"""Offline T17/T18/T19 report generation tests.

These tests build a synthetic but schema-faithful T16 run (360 attempts,
120 per registered condition, 24 development cases, five repetitions) and
verify that ``scripts.reporting`` regenerates reproducible latency reports,
quality/provenance evidence, and charts without calling Ollama or touching
sealed holdouts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from scripts.evaluation import FROZEN_THRESHOLDS, REGISTERED_CONDITIONS, load_jsonl
from scripts.reporting import ReportError, generate_reports

SEED = 20260816
CONDITIONS = ("B0_buffered_256", "I1_streaming_256", "I2_buffered_128")
ANSWER_TYPES = ("boolean", "numeric_or_date", "short_phrase", "free_form")
RUN_FILES = ("raw-traces.jsonl", "validations.jsonl", "warmups.jsonl", "run-manifest.json")


# ---------------------------------------------------------------------------
# Synthetic fixture builders
# ---------------------------------------------------------------------------

def _make_case(number: int) -> dict[str, Any]:
    answer_type = ANSWER_TYPES[number % len(ANSWER_TYPES)]
    reference = {
        "boolean": "Yes",
        "numeric_or_date": str(1900 + number),
        "short_phrase": f"answer{number}",
        "free_form": f"a free form answer for case {number}",
    }[answer_type]
    return {
        "case_id": f"eval-v1-{number:02d}",
        "source_row_id": 1000 + number,
        "question": f"Question {number}?",
        "reference_answer": reference,
        "answer_type": answer_type,
        "gold_evidence_ids": [number],
        "support_quote": reference,
        "expected_abstention": False,
        "verification_status": "manually_verified",
        "holdout": False,
    }


def _make_trace(case: Mapping[str, Any], condition_id: str, repetition: int, index: int) -> dict[str, Any]:
    """Build a complete, validate_trace-clean synthetic trace for one attempt."""
    gold_id = case["gold_evidence_ids"][0]
    # Gold evidence at rank 1; 20 retrieved passages total.
    retrieved = [f"passage:{gold_id}"] + [f"passage:{1000 + i}" for i in range(19)]
    retrieved_ranks = {evidence_id: position for position, evidence_id in enumerate(retrieved, start=1)}
    admitted = retrieved[:5]
    stream_mode = condition_id.startswith("I1")
    # Vary baseline TTC by condition to make intervention deltas observable.
    base_ttc = {"B0_buffered_256": 2000.0, "I1_streaming_256": 1800.0, "I2_buffered_128": 1700.0}[condition_id]
    ttc = base_ttc + index * 0.5
    dispatch = ttc - (0.1 + 5.0 + 15.0 + 30.0 + 5.0)
    first_displayed = {"B0_buffered_256": ttc - 3.0, "I1_streaming_256": 120.0 + index, "I2_buffered_128": ttc - 3.0}[condition_id]
    reference = case["reference_answer"]
    raw_output = json.dumps({"answer": reference, "abstained": False, "citations": ["SOURCE_1"]})
    return {
        "run_id": "t16-fixture-run",
        "trace_id": f"t16-fixture-run-{index}",
        "case_id": case["case_id"],
        "source_row_id": case["source_row_id"],
        "condition_id": condition_id,
        "repetition": repetition,
        "attempt": 1,
        "answer_type": case["answer_type"],
        "holdout": False,
        "server_state": "warm",
        "cache_state": "off",
        "stream_mode": stream_mode,
        "raw_output": raw_output,
        "retrieved_evidence_ids": retrieved,
        "admitted_evidence_ids": admitted,
        "retrieved_ranks": retrieved_ranks,
        "scores": {"citation_ids": [gold_id], "validation_valid": True},
        "fatal_gates": [],
        "finish_reason": "stop",
        "error_type": None,
        "ttfe_ms": 0.1,
        "admission_ms": 0.1,
        "retrieval_ms": 5.0,
        "context_assembly_ms": 15.0,
        "model_dispatch_to_first_token_ms": dispatch,
        "model_decode_ms": 30.0,
        "validation_ms": 5.0,
        "display_finalize_ms": 1.0,
        "ttft_ms": ttc - 35.0,
        "first_token_displayed_ms": first_displayed,
        "tta_ms": None,
        "not_applicable_reason": "no_actions",
        "ttc_ms": ttc,
        "input_tokens": 8,
        "output_tokens": 10,
        "tokens_per_second": 50.0,
        "question_length": len(str(case["question"])),
        "context_characters": 1000,
        "dataset_repo": "rag-datasets/rag-mini-wikipedia",
        "dataset_revision": "1f9f3b53fbc5995b85aab8e993504ad42c5f16f6",
        "corpus_hash": "corpus-sha",
        "index_snapshot": "index-sha",
        "model_tag": "qwen3:4b-instruct",
        "model_digest": "sha256:fixture-digest",
        "think_mode": False,
        "ollama_version": "0.32.13",
        "prompt_hash": "prompt-sha",
        "contract_hash": "contract-sha",
        "python_version": "3.12.7",
        "macos_build": "synthetic",
        "chip": "arm64",
        "ram_bytes": 25769803776,
        "power_mode": "authoritative-serial",
        "sustained_swap": False,
    }


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
            handle.write("\n")


def build_synthetic_run(
    tmp_path: Path,
    *,
    n_cases: int = 24,
    repetitions: int = 5,
    include_holdout: bool = False,
    fatal_every: int | None = None,
) -> dict[str, Path]:
    """Materialize a schema-faithful synthetic T16 run and supporting fixtures.

    Defaults produce exactly 360 valid attempts (24 cases x 3 conditions x 5
    repetitions) with zero holdout overlap. ``fatal_every`` periodically injects
    a malformed_output fatal gate; ``include_holdout`` seeds a holdout case id.
    """
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    cases_dir = tmp_path / "eval" / "v1"
    cases_dir.mkdir(parents=True)
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir(parents=True)

    cases = [_make_case(n) for n in range(1, n_cases + 1)]
    cases_path = cases_dir / "development_cases.json"
    cases_path.write_text(json.dumps(cases), encoding="utf-8")

    holdout_case_ids = [f"eval-v1-{25 + i}" for i in range(6)]
    if include_holdout:
        # Poison one case id to match a holdout id.
        cases[0]["case_id"] = holdout_case_ids[0]
        cases_path.write_text(json.dumps(cases), encoding="utf-8")
    holdout_manifest = {
        "suite_id": "text-rag-latency-eval/v1",
        "status": "sealed",
        "case_ids": holdout_case_ids,
    }
    holdout_path = cases_dir / "holdout_manifest.json"
    holdout_path.write_text(json.dumps(holdout_manifest), encoding="utf-8")

    thresholds_path = contract_dir / "thresholds.2026-08-16.json"
    thresholds_path.write_text(json.dumps(FROZEN_THRESHOLDS), encoding="utf-8")

    cases_by_id = {c["case_id"]: c for c in cases}
    traces: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    warmups: list[dict[str, Any]] = []
    index = 0
    for condition in CONDITIONS:
        stream_mode = condition.startswith("I1")
        for repetition in range(repetitions):
            for case in cases:
                trace = _make_trace(case, condition, repetition, index)
                if fatal_every is not None and index % fatal_every == 0 and index:
                    trace["raw_output"] = json.dumps({"answer": True, "abstained": False, "citations": ["SOURCE_1"]})
                    trace["scores"] = {"citation_ids": [], "validation_valid": False}
                    trace["fatal_gates"] = ["malformed_output_or_citation_schema"]
                traces.append(trace)
                validations.append({
                    "attempt": 1, "case_id": case["case_id"], "trace_id": trace["trace_id"],
                    "validation": {"fatal_gates": list(trace["fatal_gates"]), "scores": dict(trace["scores"])},
                })
                index += 1
    # Six warmups (repetition -1, baseline condition).
    for n in range(6, 12):
        case = _make_case(n)
        warmups.append(_make_trace(case, "B0_buffered_256", -1, index + n))

    _write_jsonl(run_dir / "raw-traces.jsonl", traces)
    _write_jsonl(run_dir / "validations.jsonl", validations)
    _write_jsonl(run_dir / "warmups.jsonl", warmups)
    manifest = {
        "status": "complete",
        "run_id": "t16-fixture-run",
        "command": "python -m scripts.benchmark --conditions B0_buffered_256,I1_streaming_256,I2_buffered_128",
        "attempted_count": len(traces),
        "valid_count": len(traces),
        "failure_count": 0,
        "by_condition": {c: len(traces) // len(CONDITIONS) for c in CONDITIONS},
        "lock": {"path": "run/.benchmark.lock", "pid": 12345, "acquired_at": "2026-08-16T11:25:09+00:00", "released_at": "2026-08-16T11:30:00+00:00"},
        "live_identity": {"endpoint": "http://127.0.0.1:11434", "model_digest": "sha256:fixture-digest", "ollama_version": "0.32.13"},
        "swap_observation": {"max_swap_used_bytes": 0, "sample_count": 100, "sample_interval_ms": 250, "sustained_swap": False},
        "thermal_observation": {"status": "unavailable", "reason": "no approved host thermal metric"},
        "c05": {"accepted": True, "blocking_categories": []},
    }
    (run_dir / "run-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "run_dir": run_dir,
        "output_dir": tmp_path / "reports",
        "cases_path": cases_path,
        "holdout_manifest_path": holdout_path,
        "thresholds_path": thresholds_path,
        "manifest_path": run_dir / "run-manifest.json",
    }


@pytest.fixture
def synthetic_run(tmp_path: Path) -> dict[str, Path]:
    return build_synthetic_run(tmp_path)


@pytest.fixture
def clean_run(tmp_path: Path) -> dict[str, Path]:
    """A clean run with no fatal gates, used for deterministic evidence tests."""
    return build_synthetic_run(tmp_path)


# ---------------------------------------------------------------------------
# Task 1 — T17 latency reports and manifest
# ---------------------------------------------------------------------------

def _manifest_hashes(manifest: Mapping[str, Any]) -> dict[str, str]:
    return manifest["input_hashes"]


def test_generate_reports_creates_three_latency_reports_and_manifest(synthetic_run: dict[str, Path]):
    paths = synthetic_run
    manifest = generate_reports(
        run_dir=paths["run_dir"], output_dir=paths["output_dir"],
        cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
        thresholds_path=paths["thresholds_path"],
    )

    # One latency JSON per registered condition, each reporting 120 attempts.
    for condition in ("B0_buffered_256", "I1_streaming_256", "I2_buffered_128"):
        report_path = paths["output_dir"] / f"latency.{condition}.json"
        assert report_path.exists(), f"missing {report_path}"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["metadata"]["condition_id"] == condition
        assert report["metadata"]["attempted_count"] == 120
        assert report["waterfalls"]["p50"]["ttc_ms"] == sum(
            report["waterfalls"]["p50"][stage] for stage in (
                "admission_ms", "retrieval_ms", "context_assembly_ms",
                "model_dispatch_to_first_token_ms", "model_decode_ms", "validation_ms",
            )
        )

    # The returned manifest matches what was persisted.
    manifest_path = paths["output_dir"] / "report-manifest.json"
    assert manifest_path.exists()
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted == manifest

    # Source hashes for every run artifact, development cases, holdout, thresholds.
    hashes = _manifest_hashes(manifest)
    for key in ("raw_traces", "validations", "warmups", "run_manifest",
                "development_cases", "holdout_manifest", "thresholds"):
        assert key in hashes, f"missing hash key {key}"
        assert hashes[key].startswith("sha256:") and len(hashes[key]) == 71

    # Source run identity and exact command.
    identity = manifest["source_run_identity"]
    assert identity["run_id"] == "t16-fixture-run"
    assert "command" in manifest and manifest["command"]

    # Conditions and frozen denominators.
    assert manifest["conditions"] == ["B0_buffered_256", "I1_streaming_256", "I2_buffered_128"]
    assert manifest["denominators"]["attempted"] == 360
    assert manifest["denominators"]["per_condition"] == {
        "B0_buffered_256": 120, "I1_streaming_256": 120, "I2_buffered_128": 120,
    }
    assert manifest["denominators"]["development_cases"] == 24
    assert manifest["denominators"]["repetitions"] == 5


def test_generate_reports_refuses_non_empty_output(tmp_path: Path, synthetic_run: dict[str, Path]):
    paths = synthetic_run
    (paths["output_dir"]).mkdir(parents=True, exist_ok=True)
    (paths["output_dir"] / "stale.txt").write_text("leftover", encoding="utf-8")
    with pytest.raises(ReportError, match="non-empty|empty"):
        generate_reports(
            run_dir=paths["run_dir"], output_dir=paths["output_dir"],
            cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
            thresholds_path=paths["thresholds_path"],
        )


def test_generate_reports_rejects_wrong_attempt_denominator(tmp_path: Path):
    paths = build_synthetic_run(tmp_path, n_cases=23)  # 23 * 3 * 5 = 345, not 360
    with pytest.raises(ReportError, match="360|denominator|attempt"):
        generate_reports(
            run_dir=paths["run_dir"], output_dir=paths["output_dir"],
            cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
            thresholds_path=paths["thresholds_path"],
        )


def test_generate_reports_rejects_holdout_overlap(tmp_path: Path):
    paths = build_synthetic_run(tmp_path, include_holdout=True)
    with pytest.raises(ReportError, match="holdout"):
        generate_reports(
            run_dir=paths["run_dir"], output_dir=paths["output_dir"],
            cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
            thresholds_path=paths["thresholds_path"],
        )


def test_latency_reports_are_deterministic(tmp_path: Path):
    first = build_synthetic_run(tmp_path)
    generate_reports(
        run_dir=first["run_dir"], output_dir=first["output_dir"],
        cases_path=first["cases_path"], holdout_manifest_path=first["holdout_manifest_path"],
        thresholds_path=first["thresholds_path"],
    )
    second_dir = tmp_path / "second"
    second_dir.mkdir()
    second = build_synthetic_run(second_dir)
    second["output_dir"] = second_dir / "reports"
    generate_reports(
        run_dir=second["run_dir"], output_dir=second["output_dir"],
        cases_path=second["cases_path"], holdout_manifest_path=second["holdout_manifest_path"],
        thresholds_path=second["thresholds_path"],
    )
    for condition in CONDITIONS:
        a = json.loads((first["output_dir"] / f"latency.{condition}.json").read_text(encoding="utf-8"))
        b = json.loads((second["output_dir"] / f"latency.{condition}.json").read_text(encoding="utf-8"))
        # Metrics are deterministic; only the generation command may differ by path.
        assert a["waterfalls"] == b["waterfalls"]
        assert a["marginal_stages"] == b["marginal_stages"]
        assert a["metadata"]["attempted_count"] == b["metadata"]["attempted_count"]
