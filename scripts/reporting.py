"""Offline T17/T18/T19 evidence generation from an immutable T16 run.

This module is the single offline CLI for regenerating the corrected T17 latency
reports, T18 quality/gate inputs, and T19 budget/provenance evidence from one
saved authoritative run.  It never calls Ollama, reruns a benchmark, or opens
sealed holdouts; it consumes only persisted raw traces, validation records,
warmups, and the run manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .evaluation import (
    FROZEN_CONTRACT_ID,
    REGISTERED_CONDITIONS,
    load_jsonl,
    write_condition_report,
)

SEED = 20260816
BOOTSTRAP_RESAMPLES = 10_000

DEFAULT_CASES = Path("eval/v1/development_cases.json")
DEFAULT_HOLDOUT = Path("eval/v1/holdout_manifest.json")
DEFAULT_THRESHOLDS = Path("contracts/thresholds.2026-08-16.json")

# Canonical artifacts inside an authoritative-run directory.
RUN_FILES = ("raw-traces.jsonl", "validations.jsonl", "warmups.jsonl", "run-manifest.json")
MANIFEST_NAME = "report-manifest.json"

EXPECTED_ATTEMPTS = 360
ATTEMPTS_PER_CONDITION = 120
DEVELOPMENT_CASE_COUNT = 24
REPLICATION_COUNT = 5


class ReportError(ValueError):
    """Raised when offline report inputs fail validation."""


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def _require_empty_output(output_dir: Path) -> None:
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise ReportError(f"output directory is not empty: {output_dir}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_and_validate_run(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not run_dir.is_dir():
        raise ReportError(f"run directory does not exist: {run_dir}")
    raw_path = run_dir / "raw-traces.jsonl"
    manifest_path = run_dir / "run-manifest.json"
    for filename in ("raw-traces.jsonl", "run-manifest.json"):
        if not (run_dir / filename).exists():
            raise ReportError(f"missing required run artifact {filename} in {run_dir}")
    traces = load_jsonl(raw_path)
    if len(traces) != EXPECTED_ATTEMPTS:
        raise ReportError(
            f"denominators require {EXPECTED_ATTEMPTS} attempts, found {len(traces)}"
        )
    counts = Counter(str(trace["condition_id"]) for trace in traces)
    for condition in REGISTERED_CONDITIONS:
        if counts.get(condition, 0) != ATTEMPTS_PER_CONDITION:
            raise ReportError(
                f"condition {condition} must have {ATTEMPTS_PER_CONDITION} attempts, "
                f"found {counts.get(condition, 0)}"
            )
    case_ids = {str(trace["case_id"]) for trace in traces}
    if len(case_ids) != DEVELOPMENT_CASE_COUNT:
        raise ReportError(
            f"denominators require {DEVELOPMENT_CASE_COUNT} development cases, found {len(case_ids)}"
        )
    repetitions = {trace["repetition"] for trace in traces}
    if len(repetitions) != REPLICATION_COUNT:
        raise ReportError(
            f"denominators require {REPLICATION_COUNT} repetitions, found {len(repetitions)}"
        )
    if any(trace.get("holdout") for trace in traces):
        raise ReportError("sealed holdout cases are not allowed in the development run")
    run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(run_manifest, dict):
        raise ReportError("run-manifest.json must be a JSON object")
    return traces, run_manifest


def _load_cases(cases_path: Path) -> dict[str, dict[str, Any]]:
    if not cases_path.exists():
        raise ReportError(f"development cases file does not exist: {cases_path}")
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != DEVELOPMENT_CASE_COUNT:
        raise ReportError(
            f"development cases must be exactly {DEVELOPMENT_CASE_COUNT} objects"
        )
    if not all(isinstance(case, dict) for case in data):
        raise ReportError("development cases must all be objects")
    if any(case.get("holdout") for case in data):
        raise ReportError("sealed holdout cases are not allowed in development cases")
    return {str(case["case_id"]): dict(case) for case in data}


def _load_holdout_ids(holdout_manifest_path: Path) -> set[str]:
    if not holdout_manifest_path.exists():
        raise ReportError(f"holdout manifest does not exist: {holdout_manifest_path}")
    manifest = json.loads(holdout_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ReportError("holdout manifest must be a JSON object")
    return {str(case_id) for case_id in manifest.get("case_ids", [])}


def _check_holdout_overlap(traces: Sequence[Mapping[str, Any]], holdout_ids: set[str]) -> None:
    if not holdout_ids:
        return
    overlaps = {str(trace["case_id"]) for trace in traces} & holdout_ids
    if overlaps:
        raise ReportError(
            f"sealed holdout cases cannot appear in the development run: {sorted(overlaps)}"
        )


# ---------------------------------------------------------------------------
# Manifest construction
# ---------------------------------------------------------------------------

def _input_hashes(
    run_dir: Path, cases_path: Path, holdout_manifest_path: Path, thresholds_path: Path
) -> tuple[dict[str, str], dict[str, str]]:
    hashes: dict[str, str] = {}
    paths: dict[str, str] = {}
    for key, filename in (
        ("raw_traces", "raw-traces.jsonl"),
        ("validations", "validations.jsonl"),
        ("warmups", "warmups.jsonl"),
        ("run_manifest", "run-manifest.json"),
    ):
        path = run_dir / filename
        if path.exists():
            hashes[key] = _sha256(path)
            paths[key] = str(path)
    for key, path in (
        ("development_cases", cases_path),
        ("holdout_manifest", holdout_manifest_path),
        ("thresholds", thresholds_path),
    ):
        if path.exists():
            hashes[key] = _sha256(path)
            paths[key] = str(path)
    return hashes, paths


def _output_hashes(output_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != MANIFEST_NAME:
            result[path.name] = _sha256(path)
    return result


def _source_run_identity(run_manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_manifest.get("run_id"),
        "status": run_manifest.get("status"),
        "command": run_manifest.get("command"),
        "by_condition": run_manifest.get("by_condition"),
        "c05": run_manifest.get("c05"),
        "live_identity": run_manifest.get("live_identity"),
        "swap_observation": run_manifest.get("swap_observation"),
        "thermal_observation": run_manifest.get("thermal_observation"),
    }


def _build_manifest(
    *,
    run_dir: Path,
    output_dir: Path,
    run_manifest: Mapping[str, Any],
    cases_path: Path,
    holdout_manifest_path: Path,
    thresholds_path: Path,
    command: str,
    seed: int,
    bootstrap_resamples: int,
    traces: list[dict[str, Any]],
) -> dict[str, Any]:
    input_hashes, input_paths = _input_hashes(run_dir, cases_path, holdout_manifest_path, thresholds_path)
    counts = Counter(str(trace["condition_id"]) for trace in traces)
    manifest: dict[str, Any] = {
        "schema": "offline-reporting-manifest.v1",
        "contract_id": FROZEN_CONTRACT_ID,
        "generated_at": datetime.now(UTC).isoformat(),
        "command": command,
        "seed": seed,
        "bootstrap_resamples": bootstrap_resamples,
        "run_dir": str(run_dir),
        "source_run_identity": _source_run_identity(run_manifest),
        "input_hashes": input_hashes,
        "input_paths": input_paths,
        "conditions": list(REGISTERED_CONDITIONS),
        "denominators": {
            "attempted": len(traces),
            "per_condition": {condition: counts.get(condition, 0) for condition in REGISTERED_CONDITIONS},
            "development_cases": len({str(trace["case_id"]) for trace in traces}),
            "repetitions": len({trace["repetition"] for trace in traces}),
        },
        "output_hashes": _output_hashes(output_dir),
    }
    return manifest


# ---------------------------------------------------------------------------
# Top-level report generation
# ---------------------------------------------------------------------------

def generate_reports(
    *,
    run_dir: Path,
    output_dir: Path,
    cases_path: Path = DEFAULT_CASES,
    holdout_manifest_path: Path = DEFAULT_HOLDOUT,
    thresholds_path: Path = DEFAULT_THRESHOLDS,
    seed: int = SEED,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, object]:
    """Validate a frozen T16 run and emit reproducible T17/T18/T19 evidence.

    Loads verified inputs from ``run_dir``, emits one latency JSON per registered
    condition plus the T18 quality evidence, T19 provenance evidence, charts,
    and a machine-readable manifest that hashes every input and output.
    """
    _require_empty_output(output_dir)
    traces, run_manifest = _load_and_validate_run(run_dir)
    cases_by_id = _load_cases(cases_path)
    holdout_ids = _load_holdout_ids(holdout_manifest_path)
    _check_holdout_overlap(traces, holdout_ids)

    command = f".venv/bin/python -m scripts.reporting --run-dir {run_dir} --output-dir {output_dir}"

    # T17 — per-condition latency reports.
    for condition_id in REGISTERED_CONDITIONS:
        write_condition_report(
            traces=traces,
            condition_id=condition_id,
            output_path=output_dir / f"latency.{condition_id}.json",
            bootstrap_seed=seed,
            bootstrap_resamples=bootstrap_resamples,
            cases_by_id=cases_by_id,
            command=command,
        )

    manifest = _build_manifest(
        run_dir=run_dir, output_dir=output_dir, run_manifest=run_manifest,
        cases_path=cases_path, holdout_manifest_path=holdout_manifest_path,
        thresholds_path=thresholds_path, command=command, seed=seed,
        bootstrap_resamples=bootstrap_resamples, traces=traces,
    )
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--holdout-manifest", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    args = parser.parse_args(argv)
    try:
        manifest = generate_reports(
            run_dir=args.run_dir, output_dir=args.output_dir,
            cases_path=args.cases, holdout_manifest_path=args.holdout_manifest,
            thresholds_path=args.thresholds, seed=args.seed,
            bootstrap_resamples=args.resamples,
        )
    except ReportError as exc:
        print(f"reporting blocked: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {len(manifest['output_hashes'])} reports to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
