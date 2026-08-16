"""Executable T13 contracts for the offline evaluation/reporting surface.

These tests deliberately import the future ``scripts.evaluation`` module.  T15
must implement this public API without starting Ollama, reading real holdout
outputs, or weakening any frozen gate.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.evaluation import (
    FROZEN_CONTRACT_ID,
    FROZEN_THRESHOLD_DATE,
    FROZEN_THRESHOLDS,
    REQUIRED_TRACE_FIELDS,
    aligned_waterfalls,
    build_report_metadata,
    bootstrap_by_case,
    enforce_sealed_holdout,
    evaluate_promotion,
    grade_citations,
    grade_retrieval,
    grade_text_answer,
    marginal_stage_percentiles,
    select_frozen_cases,
    summarize_quality,
    tail_analysis,
    validate_trace,
)


SEED = 20260816
CRITICAL_STAGES = (
    "admission_ms",
    "retrieval_ms",
    "context_assembly_ms",
    "model_dispatch_to_first_token_ms",
    "model_decode_ms",
    "validation_ms",
)


def issue_categories(issues: list[dict[str, object]]) -> set[str]:
    """T15 exposes machine-readable gate categories, not presentation text."""
    return {str(issue["category"]) for issue in issues}


def make_case(number: int, answer_type: str) -> dict[str, object]:
    return {
        "case_id": f"synthetic-{number:02d}",
        "source_row_id": 1000 + number,
        "question": f"Question {number}?",
        "reference_answer": "yes" if answer_type == "boolean" else f"answer {number}",
        "answer_type": answer_type,
        "gold_evidence_ids": [number],
        "support_quote": f"answer {number}",
        "expected_abstention": False,
        "verification_status": "manually_verified",
        "holdout": False,
    }


@pytest.fixture
def candidate_cases() -> list[dict[str, object]]:
    answer_types = ("boolean", "numeric_or_date", "short_phrase", "free_form")
    return [make_case(number, answer_types[number % len(answer_types)]) for number in range(40)]


@pytest.fixture
def complete_trace() -> dict[str, object]:
    trace = {
        "run_id": "run-synthetic",
        "trace_id": "trace-synthetic-01",
        "case_id": "synthetic-01",
        "source_row_id": 1001,
        "condition_id": "B0_buffered_256",
        "repetition": 0,
        "attempt": 1,
        "answer_type": "short_phrase",
        "holdout": False,
        "server_state": "warm",
        "cache_state": "off",
        "raw_output": '{"answer":"answer 1","abstained":false,"citations":["SOURCE_1"]}',
        "retrieved_evidence_ids": [1, 7],
        "admitted_evidence_ids": [1],
        "retrieved_ranks": {"1": 1},
        "admission_ms": 5.0,
        "retrieval_ms": 10.0,
        "context_assembly_ms": 15.0,
        "model_dispatch_to_first_token_ms": 20.0,
        "model_decode_ms": 25.0,
        "validation_ms": 5.0,
        "display_finalize_ms": 3.0,
        "ttfe_ms": 5.0,
        "ttft_ms": 50.0,
        "first_token_displayed_ms": 53.0,
        "tta_ms": None,
        "ttc_ms": 80.0,
        "input_tokens": 30,
        "output_tokens": 4,
        "tokens_per_second": 160.0,
        "finish_reason": "stop",
        "error_type": None,
        "dataset_repo": "rag-datasets/rag-mini-wikipedia",
        "dataset_revision": "1f9f3b53fbc5995b85aab8e993504ad42c5f16f6",
        "corpus_hash": "corpus-sha",
        "index_snapshot": "index-sha",
        "model_tag": "qwen3:4b-instruct",
        "model_digest": "sha256:model",
        "think_mode": False,
        "ollama_version": "0.32.13",
        "prompt_hash": "prompt-sha",
        "contract_hash": "contract-sha",
        "python_version": "3.12.0",
        "macos_build": "synthetic",
        "chip": "M4 Pro",
        "ram_bytes": 1,
        "power_mode": "synthetic",
        "sustained_swap": False,
        "scores": {"answer_token_f1": 1.0},
        "fatal_gates": [],
    }
    assert set(REQUIRED_TRACE_FIELDS) <= trace.keys()
    return trace


def waterfall_trace(case_id: str, ttc_ms: float, decode_ms: float, *, output_tokens: int = 4) -> dict[str, object]:
    """Produce an additive complete trace with deliberately varied stage shares."""
    trace = {
        "case_id": case_id,
        "answer_type": "short_phrase",
        "question_length": len(case_id) * 10,
        "context_length": 100,
        "output_tokens": output_tokens,
        "gold_rank": 1,
        "error_type": None,
        "truncated": False,
        "admission_ms": 5.0,
        "retrieval_ms": 10.0,
        "context_assembly_ms": 15.0,
        "model_dispatch_to_first_token_ms": ttc_ms - decode_ms - 35.0,
        "model_decode_ms": decode_ms,
        "validation_ms": 5.0,
        "ttc_ms": ttc_ms,
    }
    assert sum(trace[stage] for stage in CRITICAL_STAGES) == ttc_ms
    return trace


def test_frozen_contract_identity_and_required_trace_provenance(complete_trace: dict[str, object]):
    """A persisted result is re-gradeable only with all plan §3.3 identity fields."""
    assert FROZEN_CONTRACT_ID == "text-rag-latency/v1"
    assert FROZEN_THRESHOLD_DATE == "2026-08-16"
    assert validate_trace(complete_trace) == []

    missing_identity = deepcopy(complete_trace)
    missing_identity.pop("model_digest")
    assert "missing_required_field" in issue_categories(validate_trace(missing_identity))

    missing_inputs = deepcopy(complete_trace)
    for field in ("raw_output", "retrieved_evidence_ids", "admitted_evidence_ids", "ttc_ms", "dataset_revision"):
        missing_inputs.pop(field)
    assert "missing_required_field" in issue_categories(validate_trace(missing_inputs))


def test_fatal_gate_rejects_out_of_context_citations_and_missing_provenance(complete_trace: dict[str, object]):
    invalid_citation = deepcopy(complete_trace)
    invalid_citation["fatal_gates"] = ["citation_outside_admitted_context"]
    assert "citation_outside_admitted_context" in issue_categories(validate_trace(invalid_citation))

    thinking_enabled = deepcopy(complete_trace)
    thinking_enabled["think_mode"] = True
    assert "thinking_mode_enabled" in issue_categories(validate_trace(thinking_enabled))

    malformed = deepcopy(complete_trace)
    malformed["fatal_gates"] = ["malformed_output_or_citation_schema"]
    assert "malformed_output_or_citation_schema" in issue_categories(validate_trace(malformed))

    no_evidence = deepcopy(complete_trace)
    no_evidence["admitted_evidence_ids"] = []
    no_evidence["fatal_gates"] = ["non_abstaining_answer_with_no_admissible_evidence"]
    assert "non_abstaining_answer_with_no_admissible_evidence" in issue_categories(validate_trace(no_evidence))

    oom = deepcopy(complete_trace)
    oom["error_type"] = "oom"
    assert "model_oom" in issue_categories(validate_trace(oom))

    swapping = deepcopy(complete_trace)
    swapping["sustained_swap"] = True
    assert "sustained_swap" in issue_categories(validate_trace(swapping))


def test_seeded_dataset_selection_is_deterministic_stratified_and_keeps_holdout_sealed(candidate_cases: list[dict[str, object]]):
    first = select_frozen_cases(candidate_cases, seed=SEED, development_count=24, holdout_count=6)
    second = select_frozen_cases(candidate_cases, seed=SEED, development_count=24, holdout_count=6)

    assert first == second
    assert len(first["development"]) == 24
    assert len(first["holdout"]) == 6
    assert {case["case_id"] for case in first["development"]}.isdisjoint(
        case["case_id"] for case in first["holdout"]
    )
    assert {case["answer_type"] for case in first["development"]} == {
        "boolean", "numeric_or_date", "short_phrase", "free_form"
    }
    with pytest.raises(PermissionError, match="sealed holdout"):
        enforce_sealed_holdout(phase="development", cases=first["holdout"])


def test_deterministic_graders_measure_named_dimensions_without_model_judging():
    retrieval = grade_retrieval(retrieved_ids=[9, 4, 7, 3, 1], gold_ids=[7])
    assert retrieval == {"recall_at_1": 0.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1 / 3, "gold_rank": 3}

    citations = grade_citations(cited_ids=[7, 8], admitted_ids=[7], pinned_ids=[7, 8])
    assert citations == {"citation_precision": 0.5, "citation_validity_rate": 1.0}

    answer = grade_text_answer(answer=" YES! ", reference="yes", answer_type="boolean", finish_reason="length")
    assert answer == {
        "normalized_exact_match": 1.0,
        "answer_token_f1": 1.0,
        "task_resolution": 1.0,
        "truncated": True,
    }


def test_frozen_promotion_gate_blocks_fatal_counts_and_answer_type_slice_regressions():
    assert FROZEN_THRESHOLDS == {
        "fatal_count": 0,
        "retrieval_recall_at_5": 0.90,
        "citation_precision": 0.95,
        "citation_validity_rate": 0.98,
        "task_resolution_rate": 0.85,
        "answer_token_f1": 0.80,
        "truncation_rate_max": 0.02,
        "p95_ttft_ms": 3900,
        "p95_ttc_ms": 15000,
        "max_answer_type_slice_regression": 0.05,
        "external_runtime_api_cost_per_completed_task": 0.00,
    }
    passing = {
        "fatal_count": 0,
        "retrieval_recall_at_5": 0.90,
        "citation_precision": 0.95,
        "citation_validity_rate": 0.98,
        "task_resolution_rate": 0.85,
        "answer_token_f1": 0.80,
        "truncation_rate": 0.02,
        "p95_ttft_ms": 3900,
        "p95_ttc_ms": 15000,
        "external_runtime_api_cost_per_completed_task": 0.00,
    }
    baseline_slices = {"boolean": 0.90, "numeric_or_date": 0.90}
    candidate_slices = {"boolean": 0.85, "numeric_or_date": 0.85}
    assert evaluate_promotion(passing, baseline_slices=baseline_slices, candidate_slices=candidate_slices) == {
        "accepted": True,
        "blocking_categories": [],
    }

    fatal = {**passing, "fatal_count": 1}
    fatal_result = evaluate_promotion(fatal, baseline_slices=baseline_slices, candidate_slices=candidate_slices)
    assert fatal_result["accepted"] is False
    assert "fatal_count" in fatal_result["blocking_categories"]

    regressed_slices = {**candidate_slices, "numeric_or_date": 0.84}
    regression_result = evaluate_promotion(passing, baseline_slices=baseline_slices, candidate_slices=regressed_slices)
    assert regression_result["accepted"] is False
    assert "answer_type_slice_regression" in regression_result["blocking_categories"]


def test_quality_summary_reports_abstention_error_and_quartile_slices():
    rows = [
        {"case_id": "a", "answer_type": "boolean", "question_length": 4, "context_length": 10, "output_tokens": 1,
         "abstained": False, "error_type": None, "normalized_exact_match": 1.0, "answer_token_f1": 1.0},
        {"case_id": "b", "answer_type": "free_form", "question_length": 40, "context_length": 100, "output_tokens": 20,
         "abstained": True, "error_type": "timeout", "normalized_exact_match": 0.0, "answer_token_f1": 0.0},
    ]
    summary = summarize_quality(rows)

    assert summary["attempted_count"] == 2
    assert summary["valid_count"] == 1
    assert summary["abstention_rate"] == 0.5
    assert summary["error_rate"] == 0.5
    assert set(summary["by_answer_type"]) == {"boolean", "free_form"}
    assert set(summary["quartiles"]) == {"question_length", "context_length", "output_length"}


def test_bootstrap_resamples_independent_cases_not_latency_repetitions():
    observations = [
        {"case_id": "a", "repetition": 0, "answer_token_f1": 1.0},
        {"case_id": "a", "repetition": 1, "answer_token_f1": 1.0},
        {"case_id": "b", "repetition": 0, "answer_token_f1": 0.0},
    ]
    first = bootstrap_by_case(observations, metric="answer_token_f1", resamples=200, seed=SEED)
    second = bootstrap_by_case(list(reversed(observations)), metric="answer_token_f1", resamples=200, seed=SEED)

    assert first == second
    assert first["unit"] == "case"
    assert first["case_count"] == 2
    assert first["repetition_count"] == 3
    assert first["seed"] == SEED
    assert first["point_estimate"] == 0.5  # record-level pooling would incorrectly yield 2/3
    assert 0.0 <= first["ci_low"] <= first["ci_high"] <= 1.0


def test_percentile_aligned_waterfalls_use_real_ttc_ranked_traces_and_additive_stages():
    traces = [
        waterfall_trace("a", 60.0, 10.0),
        waterfall_trace("b", 80.0, 20.0),
        waterfall_trace("c", 100.0, 40.0),
        waterfall_trace("d", 120.0, 70.0),
        waterfall_trace("e", 140.0, 90.0),
    ]
    waterfalls = aligned_waterfalls(traces, stages=CRITICAL_STAGES)

    assert waterfalls["p50"]["case_id"] == "c"
    assert waterfalls["p95"]["case_id"] == "e"
    for percentile in ("p50", "p95"):
        selected = waterfalls[percentile]
        assert selected["ttc_ms"] == sum(selected[stage] for stage in CRITICAL_STAGES)


def test_marginal_stage_percentiles_are_explicitly_non_additive():
    traces = [
        waterfall_trace("a", 60.0, 10.0),
        waterfall_trace("b", 80.0, 20.0),
        waterfall_trace("c", 100.0, 40.0),
        waterfall_trace("d", 120.0, 70.0),
        waterfall_trace("e", 140.0, 90.0),
    ]
    table = marginal_stage_percentiles(traces, stages=CRITICAL_STAGES, seed=SEED, resamples=100)

    assert table["label"] == "marginal; columns are not additive"
    assert table["bootstrap_unit"] == "case"
    assert table["seed"] == SEED
    assert set(table["stages"]) == set(CRITICAL_STAGES)
    assert all({"p50", "p95", "ci_low", "ci_high"} <= row.keys() for row in table["stages"].values())


def test_report_metadata_preserves_reproduction_identity_and_explicit_denominators(complete_trace: dict[str, object]):
    metadata = build_report_metadata(
        traces=[complete_trace],
        condition_id="B0_buffered_256",
        attempted_count=2,
        valid_count=1,
        bootstrap_seed=SEED,
        percentile_method="nearest empirical TTC-ranked trace",
        command="python -m scripts.evaluation --condition B0_buffered_256",
    )

    assert metadata == {
        "run_ids": ["run-synthetic"],
        "condition_id": "B0_buffered_256",
        "attempted_count": 2,
        "valid_count": 1,
        "dataset_repo": "rag-datasets/rag-mini-wikipedia",
        "dataset_revision": "1f9f3b53fbc5995b85aab8e993504ad42c5f16f6",
        "corpus_hash": "corpus-sha",
        "index_snapshot": "index-sha",
        "model_tag": "qwen3:4b-instruct",
        "model_digest": "sha256:model",
        "environment": {
            "python_version": "3.12.0", "macos_build": "synthetic", "chip": "M4 Pro",
            "ram_bytes": 1, "power_mode": "synthetic", "ollama_version": "0.32.13",
        },
        "contract_hash": "contract-sha",
        "bootstrap_seed": SEED,
        "percentile_method": "nearest empirical TTC-ranked trace",
        "generation_command": "python -m scripts.evaluation --condition B0_buffered_256",
    }


def test_tail_analysis_compares_p90_or_slower_traces_to_median_cohort_with_diagnosable_fields():
    traces = [
        waterfall_trace("a", 60.0, 10.0),
        waterfall_trace("b", 70.0, 10.0),
        waterfall_trace("c", 80.0, 20.0),
        waterfall_trace("d", 90.0, 20.0),
        waterfall_trace("e", 100.0, 30.0),
        waterfall_trace("f", 110.0, 35.0),
        waterfall_trace("g", 120.0, 40.0),
        waterfall_trace("h", 130.0, 50.0),
        waterfall_trace("i", 140.0, 80.0, output_tokens=12),
        waterfall_trace("j", 200.0, 130.0, output_tokens=20),
    ]
    traces[-1]["answer_type"] = "free_form"
    traces[-1]["gold_rank"] = 5
    traces[-1]["error_type"] = "timeout"
    traces[-1]["truncated"] = True
    report = tail_analysis(traces, stages=CRITICAL_STAGES, percentile_method="nearest_rank")

    assert report["tail_threshold_percentile"] == 90
    assert report["percentile_method"] == "nearest_rank"
    assert report["tail_threshold_ttc_ms"] == 140.0
    assert [trace["case_id"] for trace in report["tail_traces"]] == ["i", "j"]
    assert report["median_cohort_method"] == "nearest_rank"
    assert report["median_cohort"]["case_id"] == "e"
    assert report["tail_stage_shares"]["model_decode_ms"] > report["median_stage_shares"]["model_decode_ms"]
    diagnostics = report["tail_diagnostics"]
    assert set(diagnostics) == {
        "answer_types", "question_lengths", "context_lengths", "output_lengths",
        "gold_ranks", "error_types", "truncated",
    }
    assert "free_form" in diagnostics["answer_types"]
    assert 20 in diagnostics["output_lengths"]
    assert 5 in diagnostics["gold_ranks"]
    assert "timeout" in diagnostics["error_types"]
    assert True in diagnostics["truncated"]
