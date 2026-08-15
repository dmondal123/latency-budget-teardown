#!/usr/bin/env python3
"""Validate the reproducibility manifest without downloading model artifacts."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate(manifest: dict, requirements: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != "environment.v1":
        errors.append("manifest schema_version must be environment.v1")
    if manifest.get("application_lock") != requirements.name:
        errors.append("application_lock must point to requirements.txt")
    target = manifest.get("target", {})
    if target.get("architecture") != "arm64":
        errors.append("target architecture must be arm64")
    if target.get("python") != "3.12.7":
        errors.append("target Python must remain pinned to 3.12.7")
    model = manifest.get("model", {})
    if not model.get("checkpoint") or not model.get("revision"):
        errors.append("model checkpoint and immutable revision are required")
    runtime = manifest.get("runtime", {})
    if runtime.get("server") != "vllm-metal":
        errors.append("runtime server must be vllm-metal")
    if manifest.get("manifest_status") == "approved_for_benchmark" and not runtime.get("server_revision"):
        errors.append("approved benchmark manifests require an immutable server revision")
    if not requirements.is_file():
        errors.append("requirements.txt is missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("environment/manifest.v1.json"))
    args = parser.parse_args()
    manifest = load(args.manifest)
    errors = validate(manifest, args.manifest.parent.parent / "requirements.txt")
    if errors:
        print("environment verification failed:", *errors, sep="\n- ", file=sys.stderr)
        return 1
    print(
        "validated environment manifest:"
        f" Python {manifest['target']['python']},"
        f" {manifest['target']['architecture']},"
        f" model {manifest['model']['checkpoint']}@{manifest['model']['revision']}"
    )
    if manifest["runtime"]["server_revision"] is None:
        print("status: runtime revision pending feasibility gate")
    print(f"host observed: {platform.system()} {platform.machine()} Python {platform.python_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
