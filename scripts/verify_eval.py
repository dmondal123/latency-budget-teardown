#!/usr/bin/env python3
"""Validate the frozen text-RAG contract and local evaluation evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.ingestion.materialize import (
    DATASET_REPOSITORY,
    DATASET_REVISION,
    normalized_corpus_hash,
)
from scripts.prepare_eval import load_arrow_rows


ANSWER_TYPES = ("boolean", "numeric_or_date", "short_phrase", "free_form")
DEVELOPMENT_ALLOCATION = Counter({"boolean": 6, "numeric_or_date": 6, "short_phrase": 6, "free_form": 6})
HOLDOUT_ALLOCATION = Counter({"boolean": 2, "numeric_or_date": 2, "short_phrase": 1, "free_form": 1})
REQUIRED_PROMOTION_PREDICATES = {
    "fatal_count", "retrieval_recall_at_5", "citation_precision", "citation_validity_rate",
    "task_resolution_rate", "answer_token_f1", "truncation_rate", "p95_ttft_ms",
    "p95_ttc_ms", "max_answer_type_slice_regression",
    "external_runtime_api_cost_per_completed_task",
}
RETIRED_TERMS = re.compile(r"pdf|multimodal|modality|traffic_slice|source_file|context_media|model_queue_prefill", re.IGNORECASE)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def validate_contract(contract: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    """Reject stale contracts and require the frozen text-RAG promotion boundary."""

    errors: list[str] = []
    allowed_statuses = {"draft_pending_g1_approval", "g1_approved"}
    if contract.get("status") not in allowed_statuses:
        errors.append("contract status must be draft_pending_g1_approval or g1_approved")
    if thresholds.get("status") != contract.get("status"):
        errors.append("threshold and contract statuses must match")
    if not contract.get("may") or not contract.get("must_not"):
        errors.append("contract must define non-empty may and must_not boundaries")
    if not contract.get("fatal_gates") or not contract.get("quality_dimensions"):
        errors.append("contract must define fatal gates and quality dimensions")
    if contract.get("approval_gate") != "G1":
        errors.append("contract approval gate must be G1")
    if thresholds.get("owner") != contract.get("owner"):
        errors.append("threshold and contract owners must match")
    try:
        date.fromisoformat(str(thresholds.get("frozen_on")))
    except (TypeError, ValueError):
        errors.append("threshold frozen_on must be an ISO date")
    predicates = thresholds.get("promotion_predicate")
    if not isinstance(predicates, Mapping) or REQUIRED_PROMOTION_PREDICATES - set(predicates):
        errors.append("thresholds are missing a required text-RAG promotion predicate")
    budget = thresholds.get("latency_budget_p95_ms")
    required_budget = {
        "admission": 100, "retrieval": 200, "context_assembly": 300,
        "model_dispatch_to_first_token": 3000, "model_decode": 11200,
        "validation": 100, "contingency": 100, "ttc": 15000,
    }
    if not isinstance(budget, Mapping) or any(budget.get(name) != value for name, value in required_budget.items()):
        errors.append("text-RAG p95 latency budget must match the frozen stage allocation")
    serialized = json.dumps({"contract": contract, "thresholds": thresholds}, sort_keys=True)
    if RETIRED_TERMS.search(serialized):
        errors.append("contract or thresholds contain retired PDF/multimodal terminology")
    return errors


def _corpus_record(dataset_manifest: Mapping[str, Any]) -> Mapping[str, Any] | None:
    configurations = dataset_manifest.get("configurations")
    if not isinstance(configurations, list):
        return None
    return next(
        (
            record for record in configurations
            if isinstance(record, Mapping)
            and record.get("config") == "text-corpus"
            and record.get("split") == "passages"
            and record.get("status", "materialized") == "materialized"
        ),
        None,
    )


def _load_pinned_passages(dataset_manifest: Mapping[str, Any]) -> tuple[dict[int, str], list[str]]:
    errors: list[str] = []
    dataset = dataset_manifest.get("dataset")
    if not isinstance(dataset, Mapping) or dataset.get("repository") != DATASET_REPOSITORY or dataset.get("revision") != DATASET_REVISION:
        return {}, ["dataset manifest does not identify the pinned text-RAG dataset revision"]
    record = _corpus_record(dataset_manifest)
    if record is None:
        return {}, ["dataset manifest lacks a materialized text-corpus/passages record"]
    files = record.get("downloaded_files")
    if not isinstance(files, list):
        return {}, ["text-corpus record lacks downloaded Arrow files"]
    arrow_path = next((Path(str(item.get("path"))) for item in files if isinstance(item, Mapping) and str(item.get("path", "")).endswith(".arrow")), None)
    if arrow_path is None or not arrow_path.is_file():
        return {}, ["pinned text-corpus Arrow file is unavailable"]
    try:
        rows = load_arrow_rows(arrow_path)
        corpus_hash, row_count = normalized_corpus_hash(rows, {"id": "integer", "passage": "string"})
    except Exception as exc:  # pragma: no cover - defensive parse boundary
        return {}, [f"unable to load pinned text-corpus Arrow file: {exc}"]
    expected_hash = record.get("normalized_corpus_sha256")
    overall_hashes = dataset_manifest.get("normalized_corpus_hashes")
    if expected_hash != corpus_hash or not isinstance(overall_hashes, Mapping) or overall_hashes.get("text-corpus") != corpus_hash:
        errors.append("pinned text-corpus hash does not match dataset manifest")
    if record.get("row_count") != row_count:
        errors.append("pinned text-corpus row count does not match dataset manifest")
    return {int(row["id"]): str(row["passage"]) for row in rows}, errors


def validate_cases(
    root: Path,
    cases: list[dict[str, Any]],
    manifest: dict[str, Any],
    case_schema: dict[str, Any],
    dataset_manifest: dict[str, Any],
) -> list[str]:
    """Validate text-RAG case shape, split, and exact local evidence support."""

    del root  # The corpus path is pinned in dataset_manifest, never inferred from the cwd.
    errors: list[str] = []
    schema_validator = Draft202012Validator(case_schema) if case_schema else None
    passages, corpus_errors = _load_pinned_passages(dataset_manifest)
    errors.extend(corpus_errors)
    if len(cases) != 30:
        errors.append(f"expected 30 cases, found {len(cases)}")
    case_ids = [case.get("case_id") for case in cases]
    if len(case_ids) != len(set(case_ids)):
        errors.append("case IDs must be unique")
    source_row_ids = [case.get("source_row_id") for case in cases]
    if len(source_row_ids) != len(set(source_row_ids)):
        errors.append("source row IDs must be unique")
    holdouts = [case for case in cases if case.get("holdout") is True]
    development = [case for case in cases if case.get("holdout") is False]
    if len(development) != 24 or len(holdouts) != 6:
        errors.append("expected 24 development and 6 sealed holdouts")
    if Counter(case.get("answer_type") for case in development) != DEVELOPMENT_ALLOCATION:
        errors.append("development cases must use the 6/6/6/6 answer-type allocation")
    if Counter(case.get("answer_type") for case in holdouts) != HOLDOUT_ALLOCATION:
        errors.append("holdout cases must use the 2/2/1/1 answer-type allocation")
    if manifest.get("status") != "sealed" or manifest.get("selection_seed") != 20260816 or not manifest.get("sealed_at"):
        errors.append("holdout manifest must be sealed with selection seed 20260816")
    if set(manifest.get("case_ids", [])) != {case.get("case_id") for case in holdouts}:
        errors.append("holdout manifest must name exactly the holdout cases")
    if len(manifest.get("case_ids", [])) != len(set(manifest.get("case_ids", []))):
        errors.append("holdout manifest case IDs must be unique")
    for case in cases:
        case_id = case.get("case_id", "<unknown>")
        if schema_validator is not None:
            schema_errors = sorted(schema_validator.iter_errors(case), key=lambda error: list(error.path))
            if schema_errors:
                errors.append(f"{case_id} violates case schema: {schema_errors[0].message}")
                continue
        if case.get("answer_type") not in ANSWER_TYPES:
            errors.append(f"{case_id} has an invalid answer type")
        if case.get("verification_status") != "manually_verified":
            errors.append(f"{case_id} is not manually verified")
        if case.get("expected_abstention") is not False:
            errors.append(f"{case_id} must be a non-abstention dataset case")
        evidence_ids = case.get("gold_evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
            errors.append(f"{case_id} must have one or more unique gold evidence IDs")
            continue
        quote = case.get("support_quote")
        if not isinstance(quote, str) or not quote.strip():
            errors.append(f"{case_id} has an empty support quote")
            continue
        found_quote = False
        for evidence_id in evidence_ids:
            passage = passages.get(evidence_id)
            if passage is None:
                errors.append(f"{case_id} gold evidence ID {evidence_id!r} is absent from pinned text corpus")
                continue
            if normalized(quote) in normalized(passage):
                found_quote = True
        if not found_quote:
            errors.append(f"{case_id} support quote is absent from its selected corpus passage")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    try:
        contract = load_json(root / "contracts/behavioral_contract.v1.json")
        thresholds = load_json(root / "contracts/thresholds.2026-08-16.json")
        development = load_json(root / "eval/v1/development_cases.json")
        holdouts = load_json(root / "eval/v1/holdout_cases.json")
        manifest = load_json(root / "eval/v1/holdout_manifest.json")
        case_schema = load_json(root / "eval/v1/case.schema.json")
        dataset_manifest = load_json(root / "eval/v1/dataset_manifest.json")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"verification failed:\n- unable to load evaluation artifact: {exc}", file=sys.stderr)
        return 1
    if not isinstance(development, list) or not isinstance(holdouts, list):
        print("verification failed:\n- case fixtures must be JSON arrays", file=sys.stderr)
        return 1
    errors = validate_contract(contract, thresholds)
    errors.extend(validate_cases(root, development + holdouts, manifest, case_schema, dataset_manifest))
    if errors:
        print("verification failed:", *errors, sep="\n- ", file=sys.stderr)
        return 1
    print("validated 30 text-RAG cases; sealed 6 holdouts; contract and thresholds are internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())