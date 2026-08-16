"""Offline T17/T18/T19 report generation tests.

These tests build a synthetic but schema-faithful T16 run (360 attempts,
120 per registered condition, 24 development cases, five repetitions) and
verify that ``scripts.reporting`` regenerates reproducible latency reports,
quality/provenance evidence, and charts without calling Ollama or touching
sealed holdouts.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Mapping

import pytest

from scripts.evaluation import FROZEN_CONTRACT_ID, FROZEN_THRESHOLDS, REGISTERED_CONDITIONS, load_jsonl
from scripts.reporting import ReportError, generate_reports

SEED = 20260816
CONDITIONS = ("B0_buffered_256", "I1_streaming_256", "I2_buffered_128")
ANSWER_TYPES = ("boolean", "numeric_or_date", "short_phrase", "free_form")
RUN_FILES = ("raw-traces.jsonl", "validations.jsonl", "warmups.jsonl", "run-manifest.json")

# Frozen promotion-gate inputs that T18 must emit per condition (see
# evaluation.evaluate_promotion comparisons and the §5 ground-truth table).
GATE_KEYS = {
    "fatal_count",
    "retrieval_recall_at_5",
    "citation_precision",
    "citation_validity_rate",
    "task_resolution_rate",
    "answer_token_f1",
    "truncation_rate",
    "p95_ttft_ms",
    "p95_ttc_ms",
    "external_runtime_api_cost_per_completed_task",
}

# Test thresholds mirror the real contract file: the flat frozen thresholds
# (used for gate inputs) plus the per-stage p95 latency budget.
TEST_THRESHOLDS = dict(FROZEN_THRESHOLDS)
TEST_THRESHOLDS["latency_budget_p95_ms"] = {
    "admission": 100,
    "retrieval": 200,
    "context_assembly": 300,
    "model_dispatch_to_first_token": 3000,
    "model_decode": 11200,
    "validation": 100,
    "contingency": 100,
    "ttc": 15000,
}

REAL_RUN_DIR = Path("artifacts/authoritative-runs/20260816T112509Z-1df7268307b1")


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
    thresholds_path.write_text(json.dumps(TEST_THRESHOLDS), encoding="utf-8")

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


# ---------------------------------------------------------------------------
# Task 2 — T18 quality evidence and T19 provenance evidence
# ---------------------------------------------------------------------------

_T18_GRADE_KEYS = {
    "recall_at_5", "mrr", "citation_precision", "citation_validity_rate",
    "answer_token_f1", "task_resolution", "truncated",
}


def _rep_zero_case_condition(record: Mapping[str, Any]) -> tuple[str, str]:
    return (str(record["case_id"]), str(record["condition_id"]))


def test_generate_reports_emits_t18_t19_evidence(synthetic_run: dict[str, Path]):
    paths = synthetic_run
    generate_reports(
        run_dir=paths["run_dir"], output_dir=paths["output_dir"],
        cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
        thresholds_path=paths["thresholds_path"],
    )

    t18_path = paths["output_dir"] / "t18-quality-evidence.json"
    t19_path = paths["output_dir"] / "t19-evidence.json"
    t19_md_path = paths["output_dir"] / "t19-evidence.md"
    assert t18_path.exists(), "missing t18-quality-evidence.json"
    assert t19_path.exists(), "missing t19-evidence.json"
    assert t19_md_path.exists(), "missing t19-evidence.md"

    t18 = json.loads(t18_path.read_text(encoding="utf-8"))
    t19 = json.loads(t19_path.read_text(encoding="utf-8"))
    md = t19_md_path.read_text(encoding="utf-8")

    # Frozen provenance identity carried through to evidence.
    assert t18["run_id"] == "t16-fixture-run"
    assert t19["run_id"] == "t16-fixture-run"
    assert t18["contract_id"] == FROZEN_CONTRACT_ID
    assert t19["contract_id"] == FROZEN_CONTRACT_ID

    # Parity: 24 cases x 3 conditions, each with 5 repetitions present.
    parity = t18["parity"]
    assert parity["complete"] is True
    assert parity["expected_replication"] == 5
    assert parity["observed_replication"] == 5
    assert parity["case_condition_pairs"] == 72

    # Exactly 72 rep-0 grade records, one per case x condition.
    rep_zero = t18["rep_zero_grades"]
    assert len(rep_zero) == 72
    assert len({r["repetition"] for r in rep_zero}) == 1
    assert next(iter({r["repetition"] for r in rep_zero})) == 0
    assert len({_rep_zero_case_condition(r) for r in rep_zero}) == 72
    for record in rep_zero:
        assert set(record["grades"].keys()) == _T18_GRADE_KEYS

    # No sealed holdout leakage into the development run.
    assert t18["holdout_overlap_count"] == 0

    # Clean synthetic fixture: gates all clear (gold at rank 1, exact answers).
    for condition in CONDITIONS:
        cond = t18["by_condition"][condition]
        assert cond["fatal_count"] == 0
        assert cond["attempted_count"] == 120
        grades = cond["grades"]
        assert grades["recall_at_5"] == 1.0
        assert grades["mrr"] == 1.0
        assert grades["citation_precision"] == 1.0
        assert grades["citation_validity_rate"] == 1.0
        assert grades["task_resolution_rate"] == 1.0
        assert grades["answer_token_f1"] == 1.0
        assert grades["truncation_rate"] == 0.0
        # All four answer types are exercised by the fixture.
        assert set(cond["answer_type_slices"]) == set(ANSWER_TYPES)
        assert set(cond["frozen_gate_inputs"]) == GATE_KEYS
        assert cond["text_unavailable_count"] == 0

    # Answer-type deltas versus B0 are emitted for both interventions.
    deltas = t18["answer_type_deltas_vs_b0"]
    assert set(deltas) == {"I1_streaming_256", "I2_buffered_128"}

    # Frozen thresholds echoed from the contract.
    assert t18["frozen_thresholds"] == FROZEN_THRESHOLDS

    # T19 tokens: synthetic fixture reports tokens, so input is available; output
    # total is non-zero and the markdown is rendered from the JSON dict.
    assert t19["tokens"]["output_tokens_total"] > 0
    assert t19["tokens"]["completed_tasks"] == 360
    assert t19["spend"]["local_runtime_serving_cost"] == 0.0
    assert t19["spend"]["agent_spend"]["available"] is False
    for condition in CONDITIONS:
        assert condition in t19["budget_variance"]
        assert "ttc" in t19["budget_variance"][condition]
        assert t19["budget_variance"][condition]["ttc"]["within_budget"] is True
        assert condition in t19["interventions"]
    assert t19["environment"]["model_tag"] == "qwen3:4b-instruct"
    # Markdown is a faithful rendering of the JSON evidence (single source).
    assert t19["run_id"] in md
    assert "$0.00" in md


def test_report_manifest_hashes_t18_t19_outputs(synthetic_run: dict[str, Path]):
    paths = synthetic_run
    manifest = generate_reports(
        run_dir=paths["run_dir"], output_dir=paths["output_dir"],
        cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
        thresholds_path=paths["thresholds_path"],
    )
    output_hashes = manifest["output_hashes"]
    for name in ("t18-quality-evidence.json", "t19-evidence.json", "t19-evidence.md"):
        assert name in output_hashes, f"manifest missing output hash for {name}"
        assert output_hashes[name].startswith("sha256:") and len(output_hashes[name]) == 71


@pytest.mark.skipif(not REAL_RUN_DIR.is_dir(), reason="real T16 run not present")
def test_real_run_t18_t19_ground_truth(tmp_path: Path):
    """Validate generated evidence against the §5 handover ground-truth table."""
    paths = {
        "run_dir": REAL_RUN_DIR,
        "output_dir": tmp_path / "real-reports",
        "cases_path": Path("eval/v1/development_cases.json"),
        "holdout_manifest_path": Path("eval/v1/holdout_manifest.json"),
        "thresholds_path": Path("contracts/thresholds.2026-08-16.json"),
    }
    generate_reports(
        run_dir=paths["run_dir"], output_dir=paths["output_dir"],
        cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
        thresholds_path=paths["thresholds_path"],
    )
    t18 = json.loads((paths["output_dir"] / "t18-quality-evidence.json").read_text(encoding="utf-8"))
    t19 = json.loads((paths["output_dir"] / "t19-evidence.json").read_text(encoding="utf-8"))

    # Parity and holdout integrity from the corrected C05 traces.
    assert t18["parity"]["complete"] is True
    assert t18["holdout_overlap_count"] == 0
    assert len(t18["rep_zero_grades"]) == 72

    expected = {
        "B0_buffered_256": {"fatal_count": 10, "recall_at_5": 0.7917, "mrr": 0.6477,
                            "citation_precision": 0.875, "citation_validity_rate": 0.6181,
                            "task_resolution_rate": 0.2727, "answer_token_f1": 0.4278,
                            "truncation_rate": 0.0},
        "I1_streaming_256": {"fatal_count": 10, "recall_at_5": 0.7917, "mrr": 0.6477,
                             "citation_precision": 0.875, "citation_validity_rate": 0.6181,
                             "task_resolution_rate": 0.2727, "answer_token_f1": 0.4278,
                             "truncation_rate": 0.0},
        "I2_buffered_128": {"fatal_count": 15, "recall_at_5": 0.7917, "mrr": 0.6477,
                            "citation_precision": 0.8333, "citation_validity_rate": 0.6042,
                            "task_resolution_rate": 0.2857, "answer_token_f1": 0.4312,
                            "truncation_rate": 0.0417},
    }
    for condition, want in expected.items():
        grades = t18["by_condition"][condition]["grades"]
        got = {
            "fatal_count": t18["by_condition"][condition]["fatal_count"],
            "recall_at_5": round(grades["recall_at_5"], 4),
            "mrr": round(grades["mrr"], 4),
            "citation_precision": round(grades["citation_precision"], 4),
            "citation_validity_rate": round(grades["citation_validity_rate"], 4),
            "task_resolution_rate": round(grades["task_resolution_rate"], 4),
            "answer_token_f1": round(grades["answer_token_f1"], 4),
            "truncation_rate": round(grades["truncation_rate"], 4),
        }
        assert got == want, f"{condition}: {got} != {want}"
        assert set(t18["by_condition"][condition]["frozen_gate_inputs"]) == GATE_KEYS

    # T17 latency report p95 values flowed into the gate inputs.
    assert t18["by_condition"]["B0_buffered_256"]["frozen_gate_inputs"]["p95_ttc_ms"] == pytest.approx(2066.28, abs=1e-2)
    assert t18["by_condition"]["B0_buffered_256"]["frozen_gate_inputs"]["p95_ttft_ms"] == pytest.approx(2065.90, abs=1e-2)

    # T19 provenance: unavailable input tokens with reason, real output totals.
    assert t19["tokens"]["input_tokens"]["available"] is False
    assert t19["tokens"]["input_tokens"]["reason"] == "not_reported_by_model"
    assert t19["tokens"]["tokens_per_second"]["available"] is False
    assert t19["tokens"]["output_tokens_total"] == 17375

    # T19 spend: free local serving, no external/agent spend.
    assert t19["spend"]["local_runtime_serving_cost"] == 0.0
    assert t19["spend"]["agent_spend"]["available"] is False

    # Interventions measured against B0 (perceived = first_token_displayed).
    interventions = t19["interventions"]
    assert interventions["I1_streaming_256"]["ttc_delta_vs_b0_ms"] == pytest.approx(-266.82, abs=1.0)
    assert interventions["I1_streaming_256"]["first_token_displayed_delta_vs_b0_ms"] == pytest.approx(-917.60, abs=1.0)
    assert interventions["I2_buffered_128"]["ttc_delta_vs_b0_ms"] == pytest.approx(-481.20, abs=1.0)

    # Environment identity from the corrected run.
    env = t19["environment"]
    assert env["model_tag"] == "qwen3:4b-instruct"
    assert env["python_version"] == "3.12.7"
    assert env["chip"] == "arm64"
    assert env["power_mode"] == "authoritative-serial"


# ---------------------------------------------------------------------------
# Task 3 — Charts, CLI, and manifest chart_metadata
# ---------------------------------------------------------------------------

_PNG_SIGNATURE = bytes.fromhex("89504e470d0a1a0a")


def test_generate_reports_emits_valid_chart_files(synthetic_run: dict[str, Path]):
    paths = synthetic_run
    manifest = generate_reports(
        run_dir=paths["run_dir"], output_dir=paths["output_dir"],
        cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
        thresholds_path=paths["thresholds_path"],
    )
    chart_metadata = manifest["chart_metadata"]
    for png_key, name in (
        ("condition_latency_png", "condition-latency.png"),
        ("waterfalls_png", "waterfalls.png"),
    ):
        png = paths["output_dir"] / name
        assert png.exists(), f"missing {name}"
        data = png.read_bytes()
        assert data[:8] == _PNG_SIGNATURE, f"{name} has invalid PNG signature"
        width, height = struct.unpack(">II", data[16:24])  # IHDR: width, height big-endian
        assert width > 0 and height > 0
        meta = chart_metadata[png_key]
        assert meta["name"] == name
        assert meta["width"] == width
        assert meta["height"] == height
        assert meta["bytes"] == len(data)


def test_manifest_chart_metadata_matches_latency_json(synthetic_run: dict[str, Path]):
    paths = synthetic_run
    manifest = generate_reports(
        run_dir=paths["run_dir"], output_dir=paths["output_dir"],
        cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
        thresholds_path=paths["thresholds_path"],
    )
    values = manifest["chart_metadata"]["waterfall_values_by_condition"]
    for condition in CONDITIONS:
        report = json.loads((paths["output_dir"] / f"latency.{condition}.json").read_text(encoding="utf-8"))
        vals = values[condition]
        assert vals["p50_ttc_ms"] == report["waterfalls"]["p50"]["ttc_ms"]
        assert vals["p95_ttc_ms"] == report["waterfalls"]["p95"]["ttc_ms"]
        assert vals["p50_first_token_displayed_ms"] == report["waterfalls"]["p50"]["first_token_displayed_ms"]
        assert vals["p95_first_token_displayed_ms"] == report["waterfalls"]["p95"]["first_token_displayed_ms"]


def test_generate_reports_writes_seven_outputs(synthetic_run: dict[str, Path]):
    paths = synthetic_run
    generate_reports(
        run_dir=paths["run_dir"], output_dir=paths["output_dir"],
        cases_path=paths["cases_path"], holdout_manifest_path=paths["holdout_manifest_path"],
        thresholds_path=paths["thresholds_path"],
    )
    expected = {
        "latency.B0_buffered_256.json", "latency.I1_streaming_256.json", "latency.I2_buffered_128.json",
        "t18-quality-evidence.json", "t19-evidence.json", "t19-evidence.md",
        "condition-latency.png", "waterfalls.png",
    }
    produced = {path.name for path in paths["output_dir"].iterdir()}
    # Six evidence + chart files plus the manifest; nothing else.
    produced.add("report-manifest.json")
    assert produced == expected | {"report-manifest.json"}, f"unexpected outputs: {produced ^ expected}"
