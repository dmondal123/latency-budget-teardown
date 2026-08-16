"""One observable retrieval → Ollama → validation request path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from .answer_validation import ValidationResult, validate_answer
from .ollama_client import OllamaClient
from .retrieval import BM25Index, assemble_context, retrieve
from .telemetry import TelemetryTrace


class PipelineError(ValueError):
    """Raised when a request cannot produce a valid, observable trace."""


def _prompt(question: str, context: str) -> str:
    return (
        "Answer only from the admitted sources. Return exactly one JSON object with "
        'keys "answer", "abstained", and "citations". Citations must use SOURCE_N labels.\n\n'
        f"Question: {question}\n\nAdmitted sources:\n{context}"
    )


def _bindings(ranked: tuple[Any, ...], admitted_ids: tuple[str, ...]) -> dict[str, int]:
    passage_ids = {item.evidence_id: item.passage_id for item in ranked}
    return {f"SOURCE_{position}": passage_ids[evidence_id] for position, evidence_id in enumerate(admitted_ids, 1)}


def run_request(
    *,
    question: str,
    index: BM25Index,
    client: OllamaClient,
    raw_fields: Mapping[str, Any],
    trace_path: str | Path,
    validation_path: str | Path,
    stream_mode: bool,
    max_tokens: int = 256,
    retrieve_k: int = 20,
    admitted_top_k: int = 5,
    character_budget: int = 12_000,
    clock: Callable[[], int] | None = None,
    display: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Execute one request, preserving retrieval evidence and all client timings."""
    if not isinstance(question, str) or not question.strip():
        raise PipelineError("question must be a non-empty string")
    if max_tokens <= 0:
        raise PipelineError("max_tokens must be positive")

    trace = TelemetryTrace(raw_fields, stream_mode=stream_mode) if clock is None else TelemetryTrace(
        raw_fields, stream_mode=stream_mode, clock=clock
    )
    trace.retrieval_started()
    ranked = retrieve(index, question, retrieve_k=retrieve_k)
    trace.ranked_passage_ids_fixed()
    context = assemble_context(ranked, admitted_top_k=admitted_top_k, character_budget=character_budget)
    if context.abstained:
        raise PipelineError("request has no admissible evidence")
    bindings = _bindings(ranked, context.admitted_evidence_ids)
    trace.record_retrieval_result(
        retrieved_evidence_ids=[item.evidence_id for item in ranked],
        admitted_evidence_ids=list(context.admitted_evidence_ids),
        retrieved_ranks={item.evidence_id: item.rank for item in ranked},
    )
    trace.request_dispatched()

    first_token_seen = False

    def on_chunk(chunk: str) -> None:
        nonlocal first_token_seen
        if not first_token_seen:
            trace.first_answer_token(chunk)
            first_token_seen = True
            if stream_mode:
                trace.first_token_displayed()
        if stream_mode and display is not None:
            display(chunk)

    result = client.generate(_prompt(question, context.text), stream=stream_mode, max_tokens=max_tokens, on_response_chunk=on_chunk)
    if not first_token_seen:
        raise PipelineError("Ollama returned no non-empty answer token")
    trace.terminal_response(raw_output=result.text, output_tokens=result.output_tokens, finish_reason=result.finish_reason)
    validation: ValidationResult = validate_answer(result.text, bindings)
    scores = {"validation_valid": validation.valid, "citation_ids": list(validation.citation_ids)}
    trace.validation_persisted(validation_path, scores=scores, fatal_gates=list(validation.fatal_gates))
    if not stream_mode:
        trace.first_token_displayed()
        if display is not None:
            display(result.text)
    trace.cli_returned()
    return trace.persist_jsonl(trace_path)
