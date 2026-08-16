"""Client-owned, reproducible latency telemetry for the RAG critical path."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Callable, Mapping


class TelemetryError(ValueError):
    """Raised when a trace does not describe an observable, valid chronology."""


class TelemetryTrace:
    """Record explicit client milestones and serialize one raw-trace JSONL row.

    Every public milestone samples the injected monotonic nanosecond clock exactly
    once.  The six TTC spans form one contiguous client-owned path; display work
    remains outside TTC.
    """

    TTC_STAGES = (
        "admission",
        "retrieval",
        "context_assembly",
        "model_dispatch_to_first_token",
        "model_decode",
        "validation",
    )
    REQUIRED_FIELDS = (
        "run_id", "trace_id", "case_id", "source_row_id", "condition_id", "repetition", "attempt",
        "answer_type", "holdout", "server_state", "cache_state", "raw_output",
        "retrieved_evidence_ids", "admitted_evidence_ids", "retrieved_ranks", "admission_ms",
        "retrieval_ms", "context_assembly_ms", "model_dispatch_to_first_token_ms",
        "model_decode_ms", "validation_ms", "display_finalize_ms", "ttfe_ms", "ttft_ms",
        "first_token_displayed_ms", "tta_ms", "ttc_ms", "input_tokens", "output_tokens",
        "tokens_per_second", "finish_reason", "error_type", "dataset_repo", "dataset_revision",
        "corpus_hash", "index_snapshot", "model_tag", "model_digest", "think_mode", "ollama_version",
        "prompt_hash", "contract_hash", "python_version", "macos_build", "chip", "ram_bytes",
        "power_mode", "scores", "fatal_gates",
    )
    _MODEL_NULLABLE_FIELDS = ("input_tokens", "output_tokens", "tokens_per_second")

    _PROVENANCE_FIELDS = (
        "run_id", "trace_id", "case_id", "source_row_id", "condition_id", "repetition", "attempt",
        "answer_type", "holdout", "server_state", "cache_state", "dataset_repo", "dataset_revision",
        "corpus_hash", "index_snapshot", "model_tag", "model_digest", "think_mode", "ollama_version",
        "prompt_hash", "contract_hash", "python_version", "macos_build", "chip", "ram_bytes", "power_mode",
    )
    _RESULT_AND_EVIDENCE_FIELDS = (
        "raw_output", "retrieved_evidence_ids", "admitted_evidence_ids", "retrieved_ranks", "scores", "fatal_gates",
    )

    def __init__(
        self,
        raw_fields: Mapping[str, Any],
        *,
        stream_mode: bool | None = None,
        clock: Callable[[], int] = perf_counter_ns,
    ):
        if not isinstance(stream_mode, bool):
            raise TelemetryError("stream_mode must be explicitly supplied as a boolean")
        self._clock = clock
        self._row: dict[str, Any] = dict(raw_fields)
        self._row["stream_mode"] = stream_mode
        self._spans_ns: dict[str, int] = {}
        self._accepted_at = self._sample_time()
        self._active_stage = "admission"
        self._stage_started_at = self._accepted_at
        self._first_token_at: int | None = None
        self._first_display_at: int | None = None
        self._validated_at: int | None = None
        self._returned_at: int | None = None
        self._terminal_error_at: int | None = None
        self._last_at = self._accepted_at

    def _sample_time(self) -> int:
        value = self._clock()
        if not isinstance(value, int):
            raise TelemetryError("clock must return integer nanoseconds")
        return value

    def _now(self) -> int:
        value = self._sample_time()
        if value < self._last_at:
            raise TelemetryError("milestone timestamps are out of order")
        self._last_at = value
        return value

    def _transition(self, expected: str, next_stage: str | None, at: int) -> None:
        if self._active_stage != expected:
            raise TelemetryError(f"expected active stage {expected!r}, got {self._active_stage!r}")
        self._spans_ns[expected] = at - self._stage_started_at
        self._active_stage = next_stage
        self._stage_started_at = at

    def retrieval_started(self) -> None:
        self._transition("admission", "retrieval", self._now())

    def ranked_passage_ids_fixed(self) -> None:
        self._transition("retrieval", "context_assembly", self._now())

    def request_dispatched(self) -> None:
        self._transition("context_assembly", "model_dispatch_to_first_token", self._now())

    def record_retrieval_result(
        self, *, retrieved_evidence_ids: list[str], admitted_evidence_ids: list[str], retrieved_ranks: Mapping[str, int]
    ) -> None:
        """Attach the immutable evidence result before model dispatch."""
        if self._active_stage != "context_assembly":
            raise TelemetryError("retrieval result must be recorded after ranking and before dispatch")
        self._row.update({
            "retrieved_evidence_ids": retrieved_evidence_ids,
            "admitted_evidence_ids": admitted_evidence_ids,
            "retrieved_ranks": dict(retrieved_ranks),
        })

    def first_answer_token(self, token: str) -> None:
        if not isinstance(token, str) or not token:
            raise TelemetryError("first answer token must be non-empty")
        at = self._now()
        self._transition("model_dispatch_to_first_token", "model_decode", at)
        self._first_token_at = at

    def first_token_displayed(self) -> None:
        if self._first_token_at is None:
            raise TelemetryError("cannot display a token before a non-empty first answer token")
        if self._first_display_at is not None:
            raise TelemetryError("first token display was already recorded")
        if self._row["stream_mode"] is False and self._validated_at is None:
            raise TelemetryError("buffered mode cannot display before validation_persisted")
        self._first_display_at = self._now()

    def terminal_response(self, **model_fields: Any) -> None:
        at = self._now()
        self._transition("model_decode", "validation", at)
        self._row.update(model_fields)

    def _append_jsonl(self, path: str | Path, payload: Mapping[str, Any]) -> None:
        try:
            serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise TelemetryError(f"telemetry payload is not JSON serializable: {exc}") from exc
        with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.write("\n")

    def validation_persisted(self, validation_record_path: str | Path, **validation_fields: Any) -> None:
        if self._active_stage != "validation":
            raise TelemetryError("validation_persisted requires a terminal response")
        validation_record = {
            "attempt": self._row.get("attempt"),
            "case_id": self._row.get("case_id"),
            "trace_id": self._row.get("trace_id"),
            "validation": validation_fields,
        }
        self._append_jsonl(validation_record_path, validation_record)
        at = self._now()
        self._transition("validation", None, at)
        self._validated_at = at
        self._row.update(validation_fields)

    def terminal_error(self, error_type: str) -> None:
        """Record an observable failed attempt without manufacturing completion spans."""
        if not isinstance(error_type, str) or not error_type:
            raise TelemetryError("terminal error requires a non-empty error_type")
        if self._terminal_error_at is not None:
            raise TelemetryError("terminal error was already recorded")
        if self._active_stage is None:
            raise TelemetryError("terminal error cannot follow validation completion")
        self._terminal_error_at = self._now()
        self._active_stage = None
        self._row["error_type"] = error_type

    def cli_returned(self) -> None:
        if self._validated_at is None and self._terminal_error_at is None:
            raise TelemetryError("cannot return before validation_persisted")
        if self._terminal_error_at is None and self._first_display_at is None:
            raise TelemetryError("cannot return before first_token_displayed")
        self._returned_at = self._now()

    @staticmethod
    def _ms(value_ns: int) -> float:
        return value_ns / 1_000_000

    def to_row(self) -> dict[str, Any]:
        failed = self._terminal_error_at is not None
        if self._active_stage is not None or self._returned_at is None or (not failed and self._validated_at is None):
            raise TelemetryError("trace is incomplete; all milestones through cli_returned are required")

        row = {field: None for field in self.REQUIRED_FIELDS}
        row.update(self._row)
        missing_provenance = [field for field in self._PROVENANCE_FIELDS if row.get(field) is None]
        if missing_provenance:
            raise TelemetryError(f"missing required provenance fields: {', '.join(missing_provenance)}")
        missing_result_fields = [field for field in self._RESULT_AND_EVIDENCE_FIELDS if row.get(field) is None]
        if missing_result_fields and not failed:
            raise TelemetryError(f"missing required result/evidence fields: {', '.join(missing_result_fields)}")
        if failed:
            for field in missing_result_fields:
                row[f"{field}_reason"] = "unavailable_due_to_terminal_error"
        for stage in self.TTC_STAGES:
            if stage in self._spans_ns:
                row[f"{stage}_ms"] = self._ms(self._spans_ns[stage])
            elif failed:
                row[f"{stage}_ms_reason"] = "unavailable_due_to_terminal_error"
            else:
                raise TelemetryError(f"trace has missing stage span: {stage}")
        if failed:
            for field in ("ttfe_ms", "ttft_ms", "first_token_displayed_ms", "display_finalize_ms", "ttc_ms"):
                row[f"{field}_reason"] = "unavailable_due_to_terminal_error"
            if "admission" in self._spans_ns:
                row["ttfe_ms"] = self._ms(self._spans_ns["admission"])
                row.pop("ttfe_ms_reason")
            if self._first_token_at is not None:
                row["ttft_ms"] = self._ms(self._first_token_at - self._accepted_at)
                row.pop("ttft_ms_reason")
            if self._first_display_at is not None:
                row["first_token_displayed_ms"] = self._ms(self._first_display_at - self._accepted_at)
                row.pop("first_token_displayed_ms_reason")
        else:
            row["display_finalize_ms"] = self._ms(self._returned_at - self._validated_at)  # type: ignore[operator]
            row["ttfe_ms"] = self._ms(self._spans_ns["admission"])
            row["ttft_ms"] = self._ms(self._first_token_at - self._accepted_at)  # type: ignore[operator]
            row["first_token_displayed_ms"] = self._ms(self._first_display_at - self._accepted_at)  # type: ignore[operator]
        row["tta_ms"] = None
        row["not_applicable_reason"] = "no_actions"
        if not failed:
            # Sum emitted stage values so JSONL consumers can verify arithmetic exactly.
            row["ttc_ms"] = sum(row[f"{stage}_ms"] for stage in self.TTC_STAGES)
        for field in self._MODEL_NULLABLE_FIELDS:
            if row[field] is None:
                row[f"{field}_reason"] = "not_reported_by_model"
        return row

    def persist_jsonl(self, path: str | Path) -> dict[str, Any]:
        """Append a deterministic UTF-8 JSONL row and return the persisted row."""
        row = self.to_row()
        self._append_jsonl(path, row)
        return row
