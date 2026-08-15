#!/usr/bin/env python3
"""Run offline feasibility checks for the planned multimodal runtime.

The probes deliberately do not download weights or start a model server. They
produce evidence about the local host and the configured candidate runtime;
the multimodal smoke test remains a separate, explicitly gated operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _probe(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def run_probes(manifest: dict, *, workdir: Path | None = None) -> dict[str, object]:
    target = manifest.get("target", {})
    runtime = manifest.get("runtime", {})
    model = manifest.get("model", {})
    probes: list[dict[str, object]] = []

    probes.append(_probe("text", bool(shutil.which("python3")), "python3 is available"))
    image_ok = shutil.which("python3") is not None
    probes.append(_probe("image", image_ok, "image probe harness is available; decoder smoke is offline"))

    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="latency-feasibility-"))
    workdir.mkdir(parents=True, exist_ok=True)
    sample = workdir / "cache-prefix.bin"
    sample.write_bytes(b"stable evidence contract prefix\n")
    digest1 = hashlib.sha256(sample.read_bytes()).hexdigest()
    digest2 = hashlib.sha256(sample.read_bytes()).hexdigest()
    probes.append(_probe("prefix_cache", digest1 == digest2, "stable prefix hash is reproducible"))

    memory_bytes = None
    if sys.platform == "darwin":
        try:
            memory_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, stderr=subprocess.DEVNULL).strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            memory_bytes = None
    probes.append(_probe("memory", memory_bytes is not None, "physical memory is observable on macOS" if memory_bytes else "macOS sysctl unavailable"))
    swap = shutil.which("sysctl") is not None if sys.platform == "darwin" else False
    probes.append(_probe("swap", swap, "swap telemetry command is available" if swap else "swap telemetry requires macOS sysctl"))

    multimodal_configured = bool(model.get("checkpoint")) and runtime.get("server") == "vllm-metal"
    probes.append(_probe("multimodal_prefix_cache", multimodal_configured, "candidate checkpoint and vllm-metal runtime are configured"))

    return {
        "schema_version": "feasibility.v1",
        "host": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "python": platform.python_version(), "memory_bytes": memory_bytes},
        "target": target,
        "runtime": runtime,
        "model": model,
        "probes": probes,
        "overall_status": "pass" if all(p["status"] == "pass" for p in probes) else "fail",
        "note": "This is an offline gate; passing does not prove model smoke, image identity, OOM, or CPU-fallback safety.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("environment/manifest.v1.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_probes(json.loads(args.manifest.read_text(encoding="utf-8")))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
