"""Serial authoritative benchmark helpers for the frozen T16 matrix and T20 holdout."""

from __future__ import annotations

import random
import argparse
import fcntl
import hashlib
import json
import os
import platform
import signal
import sys
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .evaluation import C_ACCEPTED, C_ACCEPTED_ORDER, REGISTERED_CONDITIONS, run_conditions
from .ollama_client import OllamaClient
from .pipeline import _file_hash, run_request
from .preflight_ollama import SwapSampler, model_digest, validate_local_url, version
from .retrieval import build_index
from .retrieval.run import load_manifest


class BenchmarkError(ValueError):
    """Raised when the authoritative benchmark contract is not satisfied."""


FROZEN_CONDITIONS = (
    "B0_buffered_256",
    "I1_streaming_256",
    "I2_buffered_128",
)


def validate_conditions(value: str) -> tuple[str, str, str]:
    conditions = tuple(part.strip() for part in value.split(",") if part.strip())
    if conditions != FROZEN_CONDITIONS:
        raise BenchmarkError("conditions must be the exact frozen ordered matrix")
    return FROZEN_CONDITIONS


def validate_c_accepted_conditions(value: str) -> tuple[str, str, str]:
    """Validate that the condition list is exactly ``C_accepted`` in frozen order.

    Unlike :func:`validate_conditions` (which enforces the T16 development
    matrix), this gate permits only the post-C06 accepted set — the conditions
    that passed the no-regression-vs-baseline slice gate — and is used
    exclusively for the sealed holdout benchmark (T20).
    """
    conditions = tuple(part.strip() for part in value.split(",") if part.strip())
    if set(conditions) != C_ACCEPTED or conditions != C_ACCEPTED_ORDER:
        raise BenchmarkError("conditions must be exactly C_accepted in frozen order")
    return conditions


def select_warmups(cases: Sequence[Mapping[str, Any]], *, seed: int) -> list[dict[str, Any]]:
    available = [dict(case) for case in cases if case.get("holdout") is False]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for case in available:
        by_type.setdefault(str(case.get("answer_type")), []).append(case)
    required_types = ("boolean", "numeric_or_date", "short_phrase", "free_form")
    if any(not by_type.get(answer_type) for answer_type in required_types):
        raise BenchmarkError("warmups require every frozen answer type")
    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for answer_type in required_types:
        options = sorted(by_type[answer_type], key=lambda case: str(case["case_id"]))
        rng.shuffle(options)
        selected.append(options.pop())
        by_type[answer_type] = options
    remaining = [case for answer_type in required_types for case in by_type[answer_type]]
    rng.shuffle(remaining)
    if len(remaining) < 2:
        raise BenchmarkError("warmups require six distinct development cases")
    selected.extend(remaining[:2])
    rng.shuffle(selected)
    return selected


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkError(f"expected object: {path}")
    return value


def load_development_cases(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 24 or not all(isinstance(item, dict) for item in value):
        raise BenchmarkError("development cases must be exactly 24 objects")
    if any(case.get("holdout") is not False for case in value):
        raise BenchmarkError("sealed holdout cases are not allowed")
    if len({case.get("case_id") for case in value}) != 24:
        raise BenchmarkError("development case IDs must be unique")
    return [dict(case) for case in value]


def load_holdout_cases(path: Path) -> list[dict[str, Any]]:
    """Load the six sealed holdout cases, enforcing the C06/C07 seal.

    Unlike development cases, holdout rows must carry ``holdout: true`` and
    are never mixed with development cases.  This function is the only
    code path that deserializes the sealed manifest.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 6 or not all(isinstance(item, dict) for item in value):
        raise BenchmarkError("holdout cases must be exactly six objects")
    if any(case.get("holdout") is not True for case in value):
        raise BenchmarkError("holdout cases must be marked holdout=true")
    if len({case.get("case_id") for case in value}) != 6:
        raise BenchmarkError("holdout case IDs must be unique")
    return [dict(case) for case in value]


def validate_preflight(preflight: Mapping[str, Any], *, timeout: float = 30) -> dict[str, Any]:
    identity = preflight.get("identity")
    resources = preflight.get("resource_checks")
    if preflight.get("status") != "pass" or preflight.get("local_only") is not True or preflight.get("think") is not False:
        raise BenchmarkError("preflight is not benchmark-qualified")
    if not isinstance(identity, Mapping) or not isinstance(resources, Mapping) or resources.get("sustained_swap") is not False:
        raise BenchmarkError("preflight identity or swap evidence is incomplete")
    endpoint = validate_local_url(str(preflight.get("endpoint", "")))
    expected_version, expected_digest = identity.get("ollama_version"), identity.get("model_digest")
    if not isinstance(expected_version, str) or not isinstance(expected_digest, str):
        raise BenchmarkError("preflight identity is incomplete")
    observed_version = version(endpoint, timeout)
    observed_digest = model_digest(endpoint, str(preflight.get("model", "qwen3:4b-instruct")), timeout)
    if (observed_version, observed_digest) != (expected_version, expected_digest):
        raise BenchmarkError("live Ollama identity does not match preflight")
    return {"endpoint": endpoint, "ollama_version": observed_version, "model_digest": observed_digest}


@contextmanager
def exclusive_lock(path: Path) -> Iterator[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BenchmarkError("another authoritative benchmark is running") from exc
        metadata = {"path": str(path), "pid": os.getpid(), "acquired_at": datetime.now(UTC).isoformat()}
        try:
            yield metadata
        finally:
            metadata["released_at"] = datetime.now(UTC).isoformat()
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        handle.write("\n")


def _write_manifest(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _raw_fields(
    *, run_id: str, trace_id: str, case: Mapping[str, Any], scheduled: Mapping[str, Any],
    evidence: Mapping[str, Any], preflight: Mapping[str, Any], contract: Path,
    holdout: bool = False,
) -> dict[str, Any]:
    dataset = evidence["dataset"]
    return {"run_id": run_id, "trace_id": trace_id, "case_id": case["case_id"], "source_row_id": case["source_row_id"], "condition_id": scheduled["condition_id"], "repetition": scheduled["repetition"], "attempt": 1, "answer_type": case["answer_type"], "holdout": holdout, "server_state": "holdout-qualified" if holdout else "preflight-qualified", "cache_state": "off", "dataset_repo": dataset["repository"], "dataset_revision": dataset["revision"], "corpus_hash": evidence["corpus_hash"], "index_snapshot": evidence["index_snapshot"], "model_tag": preflight.get("model", "qwen3:4b-instruct"), "model_digest": preflight["identity"]["model_digest"], "think_mode": False, "ollama_version": preflight["identity"]["ollama_version"], "prompt_hash": hashlib.sha256(b"scripts.pipeline._prompt/v1").hexdigest(), "contract_hash": _file_hash(contract), "python_version": platform.python_version(), "macos_build": platform.platform(), "chip": platform.machine(), "ram_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"), "power_mode": "holdout-serial" if holdout else "authoritative-serial"}


# ---------------------------------------------------------------------------
# T20 holdout benchmark — C_accepted against six sealed holdouts
# ---------------------------------------------------------------------------

HOLDOUT_CASE_COUNT = 6
HOLDOUT_REPETITIONS = 5
HOLDOUT_EXPECTED_ATTEMPTS = len(C_ACCEPTED_ORDER) * HOLDOUT_CASE_COUNT * HOLDOUT_REPETITIONS  # 90
HOLDOUT_EXPECTED_PER_CONDITION = HOLDOUT_CASE_COUNT * HOLDOUT_REPETITIONS  # 30


def _run_holdout(args: argparse.Namespace) -> int:
    """Run ``C_accepted`` against six sealed holdouts × five reps, exactly once.

    Serial-measurement path shared with T16 but specialized for the sealed
    holdout: loads holdout cases, uses C_accepted conditions, performs **no**
    warmups (every attempt is measured exactly once), marks every trace
    ``holdout=true``, and emits a C07 holdout manifest.
    """
    conditions = validate_c_accepted_conditions(args.conditions)
    cases = load_holdout_cases(args.holdout_cases)
    preflight = _read_object(args.preflight)
    evidence = load_manifest(args.manifest)
    live = validate_preflight(preflight)
    run_id = f"t20-{uuid.uuid4().hex}"
    run_dir = args.output_root / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{run_id[-12:]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    raw_path, validation_path = run_dir / "raw-traces.jsonl", run_dir / "validations.jsonl"
    with exclusive_lock(args.output_root / ".benchmark.lock") as lock:
        sampler = SwapSampler(); sampler.start()
        index, client = build_index(evidence), OllamaClient(base_url=live["endpoint"])

        def execute(scheduled: Mapping[str, Any], condition: Mapping[str, Any]) -> Mapping[str, Any]:
            case = next(item for item in cases if item["case_id"] == scheduled["case_id"])
            row = run_request(
                question=str(case["question"]), index=index, client=client,
                raw_fields=_raw_fields(
                    run_id=run_id, trace_id=f"{run_id}-{scheduled['ordinal']}",
                    case=case, scheduled=scheduled, evidence=evidence,
                    preflight=preflight, contract=args.contract, holdout=True,
                ),
                trace_path=raw_path, validation_path=validation_path,
                stream_mode=bool(condition["stream_mode"]),
                max_tokens=int(condition["max_tokens"]),
                persist_trace=False,
            )
            _append_jsonl(raw_path, row)
            return row

        try:
            rows = run_conditions(
                case_ids=[str(case["case_id"]) for case in cases],
                condition_ids=conditions,
                repetitions=HOLDOUT_REPETITIONS,
                seed=20260816,
                execute=execute,
            )
        finally:
            swap = sampler.stop()

        counts = {condition: sum(row["condition_id"] == condition for row in rows) for condition in conditions}
        blockers = (
            []
            if len(rows) == HOLDOUT_EXPECTED_ATTEMPTS
            and all(value == HOLDOUT_EXPECTED_PER_CONDITION for value in counts.values())
            else ["attempt_denominator"]
        )
        if swap.get("sustained_swap") is not False:
            blockers.append("sustained_swap")
        manifest = {
            "status": "complete",
            "run_id": run_id,
            "command": " ".join(sys.argv),
            "attempted_count": len(rows),
            "valid_count": sum(row.get("error_type") is None for row in rows),
            "failure_count": sum(row.get("error_type") is not None for row in rows),
            "by_condition": counts,
            "holdout_count": HOLDOUT_CASE_COUNT,
            "holdout_case_ids": [str(case["case_id"]) for case in cases],
            "repetitions": HOLDOUT_REPETITIONS,
            "c_accepted": list(conditions),
            "lock": lock,
            "live_identity": live,
            "swap_observation": swap,
            "thermal_observation": {"status": "unavailable", "reason": "no approved host thermal metric or threshold"},
            "c07": {"accepted": not blockers, "blocking_categories": blockers},
        }
        _write_manifest(run_dir / "run-manifest.json", manifest)
    return 0 if manifest["c07"]["accepted"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conditions", required=True, help=",".join(FROZEN_CONDITIONS))
    parser.add_argument("--cases", type=Path, default=Path("eval/v1/development_cases.json"))
    parser.add_argument("--holdout-cases", type=Path, default=Path("eval/v1/holdout_cases.json"))
    parser.add_argument("--preflight", type=Path, default=Path("artifacts/ollama_preflight.v1.json"))
    parser.add_argument("--manifest", type=Path, default=Path("artifacts/text_evidence_manifest.v1.json"))
    parser.add_argument("--contract", type=Path, default=Path("contracts/behavioral_contract.v1.json"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/authoritative-runs"))
    parser.add_argument("--holdout", action="store_true", help="run C_accepted against sealed holdouts (T20)")
    args = parser.parse_args(argv)
    try:
        if args.holdout:
            return _run_holdout(args)
        conditions = validate_conditions(args.conditions)
        cases, preflight, evidence = load_development_cases(args.cases), _read_object(args.preflight), load_manifest(args.manifest)
        live = validate_preflight(preflight)
        run_id = f"t16-{uuid.uuid4().hex}"
        run_dir = args.output_root / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{run_id[-12:]}"
        run_dir.mkdir(parents=True, exist_ok=False)
        raw_path, validation_path, warmup_path = run_dir / "raw-traces.jsonl", run_dir / "validations.jsonl", run_dir / "warmups.jsonl"
        with exclusive_lock(args.output_root / ".benchmark.lock") as lock:
            sampler = SwapSampler(); sampler.start()
            index, client = build_index(evidence), OllamaClient(base_url=live["endpoint"])
            def execute(scheduled: Mapping[str, Any], condition: Mapping[str, Any], *, target: Path = raw_path) -> Mapping[str, Any]:
                case = next(item for item in cases if item["case_id"] == scheduled["case_id"])
                row = run_request(question=str(case["question"]), index=index, client=client, raw_fields=_raw_fields(run_id=run_id, trace_id=f"{run_id}-{scheduled['ordinal']}", case=case, scheduled=scheduled, evidence=evidence, preflight=preflight, contract=args.contract), trace_path=raw_path, validation_path=validation_path, stream_mode=bool(condition["stream_mode"]), max_tokens=int(condition["max_tokens"]), persist_trace=False)
                _append_jsonl(target, row); return row
            try:
                for ordinal, case in enumerate(select_warmups(cases, seed=20260816), 1):
                    execute({"ordinal": f"warmup-{ordinal}", "case_id": case["case_id"], "repetition": -1, "condition_id": "B0_buffered_256"}, REGISTERED_CONDITIONS["B0_buffered_256"], target=warmup_path)
                rows = run_conditions(case_ids=[str(case["case_id"]) for case in cases], condition_ids=conditions, repetitions=5, seed=20260816, execute=execute)
            finally:
                swap = sampler.stop()
            counts = {condition: sum(row["condition_id"] == condition for row in rows) for condition in conditions}
            blockers = ([] if len(rows) == 360 and all(value == 120 for value in counts.values()) else ["attempt_denominator"])
            if swap.get("sustained_swap") is not False: blockers.append("sustained_swap")
            manifest = {"status": "complete", "run_id": run_id, "command": " ".join(sys.argv), "attempted_count": len(rows), "valid_count": sum(row.get("error_type") is None for row in rows), "failure_count": sum(row.get("error_type") is not None for row in rows), "by_condition": counts, "lock": lock, "live_identity": live, "swap_observation": swap, "thermal_observation": {"status": "unavailable", "reason": "no approved host thermal metric or threshold"}, "c05": {"accepted": not blockers, "blocking_categories": blockers}}
            _write_manifest(run_dir / "run-manifest.json", manifest)
        return 0 if manifest["c05"]["accepted"] else 1
    except (BenchmarkError, OSError, ValueError, KeyError) as exc:
        print(f"benchmark blocked: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
