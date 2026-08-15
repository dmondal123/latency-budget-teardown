#!/usr/bin/env python3
"""Validate the frozen behavioral contract and local evaluation suite."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pymupdf
from jsonschema import Draft202012Validator


REQUIRED_CASE_FIELDS = {
    "case_id", "question", "modality_group", "traffic_slice", "reference_answer",
    "required_facts", "gold_evidence_ids", "source_file", "page", "support_quote",
    "expected_abstention", "verification_status", "holdout",
}
MODALITIES = {"text", "visual", "mixed"}
SLICES = {"typical", "edge", "adversarial", "ambiguous"}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def validate_contract(contract: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("status") != "draft_pending_g1_approval":
        errors.append("contract status must remain draft_pending_g1_approval before G1")
    if not contract.get("may") or not contract.get("must_not"):
        errors.append("contract must define non-empty may and must_not boundaries")
    if not contract.get("fatal_gates") or not contract.get("quality_dimensions"):
        errors.append("contract must define fatal gates and quality dimensions")
    if thresholds.get("owner") != contract.get("owner"):
        errors.append("threshold and contract owners must match")
    try:
        date.fromisoformat(str(thresholds.get("frozen_on")))
    except ValueError:
        errors.append("threshold frozen_on must be an ISO date")
    required_thresholds = {
        "fatal_count", "retrieval_recall_at_5", "citation_precision",
        "citation_validity_rate", "task_resolution_rate", "truncation_rate",
        "p95_ttft_ms", "p95_ttc_ms", "max_modality_or_traffic_slice_regression",
        "external_runtime_api_cost_per_completed_task",
    }
    if required_thresholds - set(thresholds.get("promotion_predicate", {})):
        errors.append("thresholds are missing a required promotion predicate")
    if thresholds.get("latency_budget_p95_ms", {}).get("ttc") != 15000:
        errors.append("TTC p95 budget must be 15000 ms")
    return errors


def validate_cases(
    root: Path,
    cases: list[dict[str, Any]],
    manifest: dict[str, Any],
    case_schema: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    schema_validator = Draft202012Validator(case_schema)
    if len(cases) != 30:
        errors.append(f"expected 30 cases, found {len(cases)}")
    case_ids = [case.get("case_id") for case in cases]
    if len(case_ids) != len(set(case_ids)):
        errors.append("case IDs must be unique")
    modality_counts = Counter(case.get("modality_group") for case in cases)
    if modality_counts != Counter({"text": 10, "visual": 10, "mixed": 10}):
        errors.append(f"expected 10 cases per modality, found {dict(modality_counts)}")
    holdouts = [case for case in cases if case.get("holdout")]
    holdout_counts = Counter(case.get("modality_group") for case in holdouts)
    if len(holdouts) != 6 or holdout_counts != Counter({"text": 2, "visual": 2, "mixed": 2}):
        errors.append("expected two sealed holdouts per modality")
    if set(manifest.get("case_ids", [])) != {case["case_id"] for case in holdouts}:
        errors.append("holdout manifest must name exactly the holdout cases")
    if len({case.get("source_file") for case in cases}) < 15:
        errors.append("suite must cover at least 15 source PDFs")
    for case in cases:
        schema_errors = sorted(schema_validator.iter_errors(case), key=lambda error: list(error.path))
        if schema_errors:
            errors.append(f"{case.get('case_id', '<unknown>')} violates case schema: {schema_errors[0].message}")
            continue
        missing = REQUIRED_CASE_FIELDS - set(case)
        if missing:
            errors.append(f"{case.get('case_id', '<unknown>')} missing fields: {sorted(missing)}")
            continue
        if not all(isinstance(case[name], str) and case[name].strip() for name in ("question", "reference_answer", "support_quote")):
            errors.append(f"{case['case_id']} has an empty text field")
        if case["modality_group"] not in MODALITIES or case["traffic_slice"] not in SLICES:
            errors.append(f"{case['case_id']} has an invalid modality or traffic slice")
        if case["verification_status"] != "manually_verified" or not case["required_facts"]:
            errors.append(f"{case['case_id']} is not manually verified with required facts")
        expected_evidence_id = f"{case['source_file']}#page={case['page']}"
        if case["gold_evidence_ids"] != [expected_evidence_id]:
            errors.append(f"{case['case_id']} has an invalid gold evidence ID")
            continue
        source_path = root / case["source_file"]
        if not source_path.is_file():
            errors.append(f"{case['case_id']} source file is missing")
            continue
        document = pymupdf.open(source_path)
        if not 1 <= case["page"] <= document.page_count:
            errors.append(f"{case['case_id']} page is outside the source document")
            continue
        page_text = normalized(document[case["page"] - 1].get_text())
        if normalized(case["support_quote"]) not in page_text:
            errors.append(f"{case['case_id']} support quote is absent from its source page")
        document.close()
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.repo_root.resolve()
    contract = load_json(root / "contracts/behavioral_contract.v1.json")
    thresholds = load_json(root / "contracts/thresholds.2026-08-16.json")
    development = load_json(root / "eval/v1/development_cases.json")
    holdouts = load_json(root / "eval/v1/holdout_cases.json")
    manifest = load_json(root / "eval/v1/holdout_manifest.json")
    case_schema = load_json(root / "eval/v1/case.schema.json")
    errors = validate_contract(contract, thresholds)
    errors.extend(validate_cases(root, development + holdouts, manifest, case_schema))
    if errors:
        print("verification failed:", *errors, sep="\n- ", file=sys.stderr)
        return 1
    print("validated 30 cases; sealed 6 holdouts; contract and thresholds are internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
