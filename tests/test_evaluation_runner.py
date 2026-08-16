"""Fixed-JSONL regression contracts for the T15 benchmark runner and reports."""

from __future__ import annotations

import json

import pytest

from scripts.evaluation import (
    BASELINE_CONDITION,
    REGISTERED_CONDITIONS,
    assert_single_delta,
    interleaved_schedule,
    load_jsonl,
    validate_trace,
    write_condition_report,
)


def _trace(case_id: str, *, condition_id: str, repetition: int, ttc_ms: float) -> dict[str, object]:
    return {
        "run_id": "fixed-run",
        "trace_id": f"{condition_id}-{case_id}-{repetition}",
        "case_id": case_id,
        "source_row_id": case_id,
        "condition_id": condition_id,
        "repetition": repetition,
        "attempt": 1,
        "answer_type": "short_phrase",
        "holdout": False,
        "server_state": "warm",
        "cache_state": "off",
        "raw_output": '{"answer":"fixture","abstained":false,"citations":["SOURCE_1"]}',
        "retrieved_evidence_ids": [1],
        "admitted_evidence_ids": [1],
        "retrieved_ranks": {"1": 1},
        "admission_ms": 5.0,
        "retrieval_ms": 10.0,
        "context_assembly_ms": 15.0,
        "model_dispatch_to_first_token_ms": 20.0,
        "model_decode_ms": ttc_ms - 55.0,
        "validation_ms": 5.0,
        "display_finalize_ms": 1.0,
        "ttfe_ms": 5.0,
        "ttft_ms": 50.0,
        "first_token_displayed_ms": 51.0,
        "tta_ms": None,
        "ttc_ms": ttc_ms,
        "input_tokens": 8,
        "output_tokens": 2,
        "tokens_per_second": 20.0,
        "finish_reason": "stop",
        "error_type": None,
        "dataset_repo": "fixture-repo",
        "dataset_revision": "fixture-revision",
        "corpus_hash": "fixture-corpus",
        "index_snapshot": "fixture-index",
        "model_tag": "qwen3:4b-instruct",
        "model_digest": "fixture-digest",
        "think_mode": False,
        "ollama_version": "fixture",
        "prompt_hash": "fixture-prompt",
        "contract_hash": "fixture-contract",
        "python_version": "3.12",
        "macos_build": "fixture",
        "chip": "fixture",
        "ram_bytes": 1,
        "power_mode": "fixture",
        "sustained_swap": False,
        "scores": {"answer_token_f1": 1.0},
        "fatal_gates": [],
    }


def test_registered_conditions_have_exactly_one_declared_delta_and_reject_hidden_changes():
    for condition_id, condition in REGISTERED_CONDITIONS.items():
        assert_single_delta(condition_id, condition, baseline=BASELINE_CONDITION)

    invalid = {**REGISTERED_CONDITIONS["I2_buffered_128"], "retrieve_k": 19}
    with pytest.raises(ValueError, match="unregistered"):
        assert_single_delta("I2_buffered_128", invalid, baseline=BASELINE_CONDITION)


def test_seeded_schedule_interleaves_all_conditions_before_repeating_a_condition():
    schedule = interleaved_schedule(
        case_ids=["case-a", "case-b"],
        condition_ids=["B0_buffered_256", "I1_streaming_256", "I2_buffered_128"],
        repetitions=2,
        seed=20260816,
    )

    assert schedule == interleaved_schedule(
        case_ids=["case-a", "case-b"],
        condition_ids=["B0_buffered_256", "I1_streaming_256", "I2_buffered_128"],
        repetitions=2,
        seed=20260816,
    )
    assert len(schedule) == 12
    for offset in range(0, len(schedule), 3):
        assert {row["condition_id"] for row in schedule[offset:offset + 3]} == set(REGISTERED_CONDITIONS)


def test_fixed_jsonl_regenerates_machine_readable_waterfalls_and_marginal_table(tmp_path):
    rows = [
        _trace("case-a", condition_id="B0_buffered_256", repetition=0, ttc_ms=80.0),
        _trace("case-b", condition_id="B0_buffered_256", repetition=0, ttc_ms=100.0),
        _trace("case-c", condition_id="B0_buffered_256", repetition=0, ttc_ms=120.0),
    ]
    trace_path = tmp_path / "fixed.jsonl"
    trace_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

    loaded = load_jsonl(trace_path)
    report_path = tmp_path / "report.json"
    report = write_condition_report(
        traces=loaded,
        condition_id="B0_buffered_256",
        output_path=report_path,
        bootstrap_seed=20260816,
        bootstrap_resamples=100,
        command="python -m scripts.evaluation report --input fixed.jsonl",
    )

    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["waterfalls"]["p50"]["case_id"] == "case-b"
    assert report["waterfalls"]["p95"]["case_id"] == "case-c"
    assert report["marginal_stages"]["label"] == "marginal; columns are not additive"
    assert report["metadata"]["attempted_count"] == 3
    assert report["metadata"]["valid_count"] == 3


def test_successful_trace_with_missing_raw_evidence_or_timing_is_not_reportable():
    trace = _trace("case-a", condition_id="B0_buffered_256", repetition=0, ttc_ms=80.0)
    trace["raw_output"] = None
    trace["retrieved_evidence_ids"] = None
    trace["ttc_ms"] = None

    categories = {issue["category"] for issue in validate_trace(trace)}

    assert "missing_required_value" in categories
