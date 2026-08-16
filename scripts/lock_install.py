#!/usr/bin/env python3
"""Prove that the checked-in requirements lock installs in isolated Python 3.12."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements.txt"
SOURCE = ROOT / "requirements.in"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: Sequence[str], *, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def find_python() -> Path:
    candidates = [ROOT / ".venv" / "bin" / "python", Path("python3.12")]
    for candidate in candidates:
        resolved = shutil.which(str(candidate)) if not candidate.is_absolute() else candidate
        if resolved and Path(resolved).exists():
            probe = subprocess.run(
                [str(resolved), "-c", "import sys; print(sys.version_info[:2])"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if probe.returncode == 0 and probe.stdout.strip() == "(3, 12)":
                return Path(resolved).resolve()
    raise RuntimeError("Python 3.12 interpreter not found; tried .venv/bin/python and python3.12")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "lock.v1.json")
    args = parser.parse_args()

    result: dict[str, object] = {
        "schema_version": "lock-proof.v1",
        "source": str(SOURCE.relative_to(ROOT)),
        "lock": str(LOCK.relative_to(ROOT)),
        "source_sha256": sha256(SOURCE),
        "lock_sha256": sha256(LOCK),
        "status": "failed",
    }
    try:
        python = find_python()
        uv = shutil.which("uv")
        if not uv:
            raise RuntimeError("uv executable not found on PATH")
        result["python"] = str(python)
        result["python_version"] = subprocess.check_output(
            [str(python), "--version"], text=True
        ).strip()
        result["uv_version"] = subprocess.check_output([uv, "--version"], text=True).strip()

        with tempfile.TemporaryDirectory(prefix="week-1-fde-lock-") as temp:
            temp_dir = Path(temp)
            venv_dir = temp_dir / "venv"
            env = os.environ.copy()
            env["UV_CACHE_DIR"] = str(temp_dir / "uv-cache")

            create = run([uv, "venv", "--python", str(python), str(venv_dir)], env=env, cwd=ROOT)
            result["venv_command"] = [uv, "venv", "--python", str(python), str(venv_dir)]
            result["venv_output"] = create.stdout[-4000:]
            if create.returncode:
                raise RuntimeError(f"uv venv failed with exit {create.returncode}")

            isolated_python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            install_command = [uv, "pip", "install", "--python", str(isolated_python), "-r", str(LOCK)]
            install = run(install_command, env=env, cwd=ROOT)
            result["install_command"] = install_command
            result["install_output"] = install.stdout[-8000:]
            result["install_exit_code"] = install.returncode
            if install.returncode:
                raise RuntimeError(f"uv pip install failed with exit {install.returncode}")

            freeze = run([uv, "pip", "freeze", "--python", str(isolated_python)], env=env, cwd=ROOT)
            result["freeze_output"] = freeze.stdout
            if freeze.returncode:
                raise RuntimeError(f"uv pip freeze failed with exit {freeze.returncode}")
            result["status"] = "passed"
            result["isolation"] = "temporary directory outside repository"
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        result["error"] = str(error)
        exit_code = 1
    else:
        exit_code = 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output), "error": result.get("error")}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
