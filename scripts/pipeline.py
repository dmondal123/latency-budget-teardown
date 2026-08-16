"""One observable retrieval → Ollama → validation request path."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from .answer_validation import ValidationResult, validate_answer
from .ollama_client import OllamaClient, OllamaClientError
from .retrieval import BM25Index, RetrievalError, assemble_context, build_index, retrieve
from .retrieval.run import load_manifest
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

    trace_fields = {**raw_fields, "question_length": len(question)}
    trace = TelemetryTrace(trace_fields, stream_mode=stream_mode) if clock is None else TelemetryTrace(
        trace_fields, stream_mode=stream_mode, clock=clock
    )
    trace.retrieval_started()
    ranked = retrieve(index, question, retrieve_k=retrieve_k)
    trace.ranked_passage_ids_fixed()
    context = assemble_context(ranked, admitted_top_k=admitted_top_k, character_budget=character_budget)
    if context.abstained:
        raise PipelineError("request has no admissible evidence")
    bindings = _bindings(ranked, context.admitted_evidence_ids)
    trace.record_context_characters(len(context.text))
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


def _read_object(path: Path, *, description: str) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise PipelineError(f"{description} must be a JSON object")
    return value


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manual_fields(
    *, manifest: Mapping[str, Any], preflight: Mapping[str, Any], contract_path: Path, run_id: str, trace_id: str,
    stream_mode: bool, max_tokens: int
) -> dict[str, Any]:
    dataset = manifest.get("dataset")
    identity = preflight.get("identity")
    if not isinstance(dataset, Mapping) or not isinstance(identity, Mapping):
        raise PipelineError("manifest dataset and preflight identity are required")
    if preflight.get("think") is not False:
        raise PipelineError("preflight must prove thinking is disabled")
    repository, revision = dataset.get("repository"), dataset.get("revision")
    model_digest, ollama_version = identity.get("model_digest"), identity.get("ollama_version")
    if not all(isinstance(value, str) and value for value in (repository, revision, model_digest, ollama_version)):
        raise PipelineError("manual query provenance is incomplete")
    return {
        "run_id": run_id, "trace_id": trace_id, "case_id": trace_id, "source_row_id": "manual-query",
        "condition_id": f"manual_{'streamed' if stream_mode else 'buffered'}_{max_tokens}", "repetition": 1, "attempt": 1,
        "answer_type": "manual", "holdout": False, "server_state": "manual", "cache_state": "off",
        "dataset_repo": repository, "dataset_revision": revision, "corpus_hash": manifest.get("corpus_hash"),
        "index_snapshot": manifest.get("index_snapshot"), "model_tag": preflight.get("model", "qwen3:4b-instruct"),
        "model_digest": model_digest, "think_mode": False, "ollama_version": ollama_version,
        "prompt_hash": hashlib.sha256(b"scripts.pipeline._prompt/v1").hexdigest(), "contract_hash": _file_hash(contract_path),
        "python_version": platform.python_version(), "macos_build": platform.platform(), "chip": platform.machine(),
        "ram_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"), "power_mode": "manual-query",
    }


def main(argv: list[str] | None = None) -> int:
    """Run one local, validated RAG query and print only the accepted model JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--preflight", type=Path, default=Path("artifacts/ollama_preflight.v1.json"))
    parser.add_argument("--contract", type=Path, default=Path("contracts/behavioral_contract.v1.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/manual-queries"))
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--retrieve-k", type=int, default=20)
    parser.add_argument("--admitted-top-k", type=int, default=5)
    parser.add_argument("--character-budget", type=int, default=12_000)
    args = parser.parse_args(argv)
    run_id, trace_id = f"manual-{uuid.uuid4().hex}", f"trace-{uuid.uuid4().hex}"
    try:
        manifest = load_manifest(args.manifest)
        preflight = _read_object(args.preflight, description="preflight")
        index = build_index(manifest)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        fields = _manual_fields(
            manifest=manifest, preflight=preflight, contract_path=args.contract, run_id=run_id, trace_id=trace_id,
            stream_mode=args.stream, max_tokens=args.max_tokens,
        )
        row = run_request(
            question=args.question, index=index, client=OllamaClient(), raw_fields=fields,
            trace_path=args.output_dir / f"{trace_id}.trace.jsonl", validation_path=args.output_dir / f"{trace_id}.validation.jsonl",
            stream_mode=args.stream, max_tokens=args.max_tokens, retrieve_k=args.retrieve_k,
            admitted_top_k=args.admitted_top_k, character_budget=args.character_budget,
        )
    except (OSError, json.JSONDecodeError, RetrievalError, OllamaClientError, PipelineError, ValueError) as exc:
        print(f"query blocked: {exc}", file=sys.stderr)
        return 2
    if not row["scores"]["validation_valid"]:
        print(f"query rejected by validation: {', '.join(row['fatal_gates'])}", file=sys.stderr)
        return 3
    print(row["raw_output"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
