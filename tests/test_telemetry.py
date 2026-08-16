"""Client-owned latency telemetry contracts."""

import json

import pytest

from scripts.telemetry import TelemetryError, TelemetryTrace


class Clock:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


def raw_fields(**overrides):
    fields = {
        "run_id": "run-1", "trace_id": "trace-1", "case_id": "case-1", "source_row_id": "source-1",
        "condition_id": "condition-1", "repetition": 1, "attempt": 1, "answer_type": "short",
        "holdout": False, "server_state": "warm", "cache_state": "cold", "dataset_repo": "repo",
        "dataset_revision": "revision", "corpus_hash": "corpus", "index_snapshot": "index",
        "model_tag": "model", "model_digest": "digest", "think_mode": False, "ollama_version": "version",
        "prompt_hash": "prompt", "contract_hash": "contract", "python_version": "3.12",
        "macos_build": "build", "chip": "chip", "ram_bytes": 1, "power_mode": "normal",
        "raw_output": "answer", "retrieved_evidence_ids": ["passage-1"],
        "admitted_evidence_ids": ["passage-1"], "retrieved_ranks": {"passage-1": 1},
        "scores": {"grounded": True}, "fatal_gates": [],
        "custom_identity": "retained",
    }
    fields.update(overrides)
    return fields


def complete_trace(clock, *, stream_mode, validation_path, raw=None):
    trace = TelemetryTrace(
        raw_fields() if raw is None else raw,
        stream_mode=stream_mode,
        clock=clock,
    )
    trace.retrieval_started()
    trace.ranked_passage_ids_fixed()
    trace.request_dispatched()
    trace.first_answer_token("answer")
    if stream_mode:
        trace.first_token_displayed()
    trace.terminal_response()
    trace.validation_persisted(validation_path, scores={"grounded": True})
    if not stream_mode:
        trace.first_token_displayed()
    trace.cli_returned()
    return trace


def test_complete_trace_has_exclusive_stage_arithmetic_and_client_clocks(tmp_path):
    # A missing boundary between any two critical stages must make this fail.
    trace = complete_trace(Clock([0, 10, 30, 60, 100, 150, 210, 260, 300]), stream_mode=True,
                           validation_path=tmp_path / "validation.jsonl")

    row = trace.to_row()

    assert {name: row[f"{name}_ms"] for name in TelemetryTrace.TTC_STAGES} == {
        "admission": 0.00001,
        "retrieval": 0.00002,
        "context_assembly": 0.00003,
        "model_dispatch_to_first_token": 0.00004,
        "model_decode": 0.00011,
        "validation": 0.00005,
    }
    assert row["ttfe_ms"] == 0.00001
    assert row["ttft_ms"] == 0.0001
    assert row["first_token_displayed_ms"] == 0.00015
    assert row["ttc_ms"] == sum(row[f"{name}_ms"] for name in TelemetryTrace.TTC_STAGES)
    assert row["tta_ms"] is None
    assert row["not_applicable_reason"] == "no_actions"
    assert row["display_finalize_ms"] == 0.00004


def test_first_token_displayed_uses_real_display_event_in_each_mode(tmp_path):
    # Treating buffered display as first-token receipt must make this fail.
    streamed = complete_trace(Clock([0, 10, 30, 60, 100, 150, 210, 260, 300]), stream_mode=True,
                              validation_path=tmp_path / "streamed-validation.jsonl")
    buffered = complete_trace(Clock([0, 10, 30, 60, 100, 150, 210, 260, 300]), stream_mode=False,
                              validation_path=tmp_path / "buffered-validation.jsonl")

    assert streamed.to_row()["first_token_displayed_ms"] == 0.00015
    assert buffered.to_row()["first_token_displayed_ms"] == 0.00026
    assert streamed.to_row()["ttft_ms"] == buffered.to_row()["ttft_ms"] == 0.0001


def test_rejects_invalid_chronology_and_empty_first_token():
    # Removing milestone-order validation must make this fail.
    trace = TelemetryTrace(raw_fields(trace_id="invalid"), stream_mode=True, clock=Clock([0, 10, 20, 30, 40]))
    with pytest.raises(TelemetryError, match="active stage"):
        trace.request_dispatched()
    trace.retrieval_started()
    trace.ranked_passage_ids_fixed()
    trace.request_dispatched()
    with pytest.raises(TelemetryError, match="non-empty"):
        trace.first_answer_token("")
    with pytest.raises(TelemetryError, match="incomplete"):
        trace.to_row()


def test_buffered_trace_rejects_display_before_validation():
    # Removing the buffered display boundary must make this fail.
    trace = TelemetryTrace(raw_fields(trace_id="buffered"), stream_mode=False, clock=Clock([0, 10, 20, 30, 40, 50]))
    trace.retrieval_started()
    trace.ranked_passage_ids_fixed()
    trace.request_dispatched()
    trace.first_answer_token("answer")

    with pytest.raises(TelemetryError, match="buffered"):
        trace.first_token_displayed()


def test_requires_explicit_validated_display_mode():
    # Allowing an absent/ambiguous display mode must make this fail.
    with pytest.raises(TelemetryError, match="stream_mode"):
        TelemetryTrace(raw_fields(trace_id="mode"), clock=Clock([0]))
    with pytest.raises(TelemetryError, match="stream_mode"):
        TelemetryTrace(raw_fields(trace_id="mode"), stream_mode="streamed", clock=Clock([0]))


def test_persists_deterministic_jsonl_with_required_fields(tmp_path):
    # Omitting raw identity, terminal null reasons, or the newline must make this fail.
    path = tmp_path / "trace.jsonl"
    trace = complete_trace(Clock([0, 10, 30, 60, 100, 150, 210, 260, 300]), stream_mode=False,
                           validation_path=tmp_path / "validation.jsonl")
    trace.persist_jsonl(path)
    trace.persist_jsonl(path)

    content = path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in content.splitlines()]
    row = rows[0]
    assert content.endswith("\n")
    assert rows[0] == rows[1]
    assert row["trace_id"] == "trace-1"
    assert row["custom_identity"] == "retained"
    assert row["input_tokens"] is None
    assert row["input_tokens_reason"] == "not_reported_by_model"
    assert row["output_tokens"] is None
    assert row["tokens_per_second"] is None
    assert row["tokens_per_second_reason"] == "not_reported_by_model"
    assert set(TelemetryTrace.REQUIRED_FIELDS).issubset(row)
    validation_rows = [json.loads(line) for line in (tmp_path / "validation.jsonl").read_text().splitlines()]
    assert validation_rows == [{"attempt": 1, "case_id": "case-1", "trace_id": "trace-1",
                               "validation": {"scores": {"grounded": True}}}]


def test_terminal_error_persists_a_complete_failed_attempt_without_invented_spans(tmp_path):
    trace = TelemetryTrace(raw_fields(raw_output=None, retrieved_evidence_ids=None, admitted_evidence_ids=None,
                                     retrieved_ranks=None, scores=None, fatal_gates=None), stream_mode=True,
                           clock=Clock([0, 10, 30, 60, 100, 150]))
    trace.retrieval_started()
    trace.ranked_passage_ids_fixed()
    trace.request_dispatched()
    trace.terminal_error("timeout")
    trace.cli_returned()
    trace.persist_jsonl(tmp_path / "failed.jsonl")

    row = trace.to_row()
    assert row["error_type"] == "timeout"
    assert row["admission_ms"] == 0.00001
    assert row["ttfe_ms"] == 0.00001
    assert "ttfe_ms_reason" not in row
    assert row["retrieval_ms"] == 0.00002
    assert row["context_assembly_ms"] == 0.00003
    for field in ("model_dispatch_to_first_token_ms", "model_decode_ms", "validation_ms", "ttft_ms",
                  "first_token_displayed_ms", "display_finalize_ms", "ttc_ms"):
        assert row[field] is None
        assert row[f"{field}_reason"] == "unavailable_due_to_terminal_error"
    for field in TelemetryTrace._RESULT_AND_EVIDENCE_FIELDS:
        assert row[field] is None
        assert row[f"{field}_reason"] == "unavailable_due_to_terminal_error"


def test_rejects_decreasing_clock_duplicate_terminal_and_missing_provenance(tmp_path):
    decreasing = TelemetryTrace(raw_fields(), stream_mode=True, clock=Clock([10, 9]))
    with pytest.raises(TelemetryError, match="out of order"):
        decreasing.retrieval_started()

    duplicate = TelemetryTrace(raw_fields(), stream_mode=True, clock=Clock([0, 10, 20, 30, 40, 50]))
    duplicate.retrieval_started()
    duplicate.ranked_passage_ids_fixed()
    duplicate.request_dispatched()
    duplicate.terminal_error("network")
    with pytest.raises(TelemetryError, match="terminal error"):
        duplicate.terminal_error("network")

    display = TelemetryTrace(raw_fields(), stream_mode=True, clock=Clock([0, 10, 20, 30, 40, 50]))
    display.retrieval_started()
    display.ranked_passage_ids_fixed()
    display.request_dispatched()
    display.first_answer_token("answer")
    display.first_token_displayed()
    with pytest.raises(TelemetryError, match="already"):
        display.first_token_displayed()

    missing = complete_trace(Clock([0, 10, 30, 60, 100, 150, 210, 260, 300]), stream_mode=True,
                             validation_path=tmp_path / "missing-validation.jsonl", raw=raw_fields(case_id=None))
    with pytest.raises(TelemetryError, match="provenance"):
        missing.to_row()


def test_success_trace_rejects_missing_result_and_evidence_fields(tmp_path):
    trace = complete_trace(Clock([0, 10, 30, 60, 100, 150, 210, 260, 300]), stream_mode=True,
                           validation_path=tmp_path / "validation.jsonl", raw=raw_fields(raw_output=None))
    with pytest.raises(TelemetryError, match="result/evidence"):
        trace.to_row()
