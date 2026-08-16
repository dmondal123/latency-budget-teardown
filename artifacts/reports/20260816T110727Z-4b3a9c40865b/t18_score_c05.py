#!/usr/bin/env python3
"""Trace-only T18 quality evidence using the public deterministic graders.

This intentionally does not invoke the benchmark, Ollama, or any service.
It selects repetition 0 as the single prespecified output for each
development case/condition and verifies parity across the five saved traces.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.evaluation import grade_citations, grade_retrieval, grade_text_answer, validate_trace


CONDITIONS = ("B0_buffered_256", "I1_streaming_256", "I2_buffered_128")
ANSWER_TYPES = ("boolean", "numeric_or_date", "short_phrase", "free_form")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_line, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            row = json.loads(line)
            row["_source_line"] = source_line
            rows.append(row)
    return rows


def passage_id(value: object) -> int:
    return int(str(value).split(":")[-1])


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def answer_payload(raw_output: object) -> dict[str, Any] | None:
    try:
        payload = json.loads(str(raw_output))
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("answer"), str):
        return None
    return payload


def score_row(row: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    retrieved = [passage_id(value) for value in row["retrieved_evidence_ids"]]
    admitted = [passage_id(value) for value in row["admitted_evidence_ids"]]
    cited = [int(value) for value in row.get("scores", {}).get("citation_ids", [])]
    payload = answer_payload(row.get("raw_output"))
    text = grade_text_answer(
        answer=payload["answer"] if payload else "",
        reference=str(case["reference_answer"]),
        answer_type=str(case["answer_type"]),
        finish_reason=row.get("finish_reason"),
    )
    retrieval = grade_retrieval(retrieved_ids=retrieved, gold_ids=case["gold_evidence_ids"])
    # Every cited ID must be an admitted, trace-resolved passage. The item-level
    # denominator remains explicit: zero-citation rows are not silently scored 1.
    citations = grade_citations(cited_ids=cited, admitted_ids=admitted, pinned_ids=retrieved)
    return {
        "case_id": row["case_id"], "answer_type": case["answer_type"],
        "source_line": row["_source_line"], "raw_output_parseable": payload is not None,
        "schema_valid": row.get("scores", {}).get("validation_valid") is True,
        "fatal_gates": row.get("fatal_gates", []), "cited_item_count": len(cited),
        **retrieval, **text, **citations,
    }


def metric_summary(scored: list[dict[str, Any]]) -> dict[str, Any]:
    citations = [row for row in scored if row["cited_item_count"]]
    cited_items = sum(row["cited_item_count"] for row in scored)
    return {
        "case_denominator": len(scored),
        "retrieval_recall_at_1": mean([row["recall_at_1"] for row in scored]),
        "retrieval_recall_at_3": mean([row["recall_at_3"] for row in scored]),
        "retrieval_recall_at_5": mean([row["recall_at_5"] for row in scored]),
        "mrr": mean([row["mrr"] for row in scored]),
        "zero_gold_retrieval_count": sum(row["gold_rank"] == 0 for row in scored),
        "normalized_exact_match": mean([row["normalized_exact_match"] for row in scored]),
        "answer_token_f1": mean([row["answer_token_f1"] for row in scored]),
        "task_resolution_rate": mean([row["task_resolution"] for row in scored]),
        "truncation_rate": mean([float(row["truncated"]) for row in scored]),
        "schema_validity_rate": mean([float(row["schema_valid"]) for row in scored]),
        "raw_output_parseability_rate": mean([float(row["raw_output_parseable"]) for row in scored]),
        "fatal_gate_row_count": sum(bool(row["fatal_gates"]) for row in scored),
        "fatal_gate_count": sum(len(row["fatal_gates"]) for row in scored),
        "citation_item_denominator": cited_items,
        "citation_row_denominator_nonempty": len(citations),
        "zero_citation_row_count": len(scored) - len(citations),
        "citation_precision": (
            sum(row["citation_precision"] * row["cited_item_count"] for row in citations) / cited_items
            if cited_items else None
        ),
        "citation_validity_rate": (
            sum(row["citation_validity_rate"] * row["cited_item_count"] for row in citations) / cited_items
            if cited_items else None
        ),
    }


def parity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_condition_case: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_condition_case[(row["condition_id"], row["case_id"])].append(row)
    violations: list[dict[str, Any]] = []
    for (condition, case_id), values in sorted(by_condition_case.items()):
        signatures = {
            json.dumps({key: row.get(key) for key in ("raw_output", "finish_reason", "fatal_gates", "scores")}, sort_keys=True)
            for row in values
        }
        if len(values) != 5 or len(signatures) != 1:
            violations.append({"condition_id": condition, "case_id": case_id, "trace_count": len(values), "signature_count": len(signatures)})
    return {"expected_traces_per_case_condition": 5, "case_condition_count": len(by_condition_case), "violation_count": len(violations), "violations": violations}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--holdout-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = load_jsonl(args.input)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    holdout_manifest = json.loads(args.holdout_manifest.read_text(encoding="utf-8"))
    if len(cases) != 24 or any(case.get("holdout") is not False for case in cases):
        raise ValueError("T18 requires exactly the 24 development cases")
    cases_by_id = {str(case["case_id"]): case for case in cases}
    if len(cases_by_id) != 24:
        raise ValueError("development case IDs must be unique")
    sealed_ids = set(holdout_manifest["case_ids"])
    trace_case_ids = {str(row["case_id"]) for row in rows}
    if trace_case_ids != set(cases_by_id) or trace_case_ids & sealed_ids or any(row.get("holdout") is not False for row in rows):
        raise ValueError("trace cases do not exactly match unsealed development cases")
    if len(rows) != 360 or Counter(row["condition_id"] for row in rows) != Counter({condition: 120 for condition in CONDITIONS}):
        raise ValueError("C05 trace denominator is not 360 = 3 conditions * 24 cases * 5 repetitions")
    selected = [row for row in rows if row["repetition"] == 0]
    if len(selected) != 72:
        raise ValueError("expected one repetition-0 trace for each condition/case")
    identities = {key: sorted({str(row.get(key)) for row in rows}) for key in ("run_id", "contract_hash", "dataset_repo", "dataset_revision", "corpus_hash", "index_snapshot", "model_tag", "model_digest", "think_mode", "power_mode")}
    validation_issues = [{"trace_id": row["trace_id"], "source_line": row["_source_line"], "categories": [issue["category"] for issue in validate_trace(row)]} for row in rows]
    validation_issues = [issue for issue in validation_issues if issue["categories"]]
    by_condition: dict[str, Any] = {}
    arithmetic_checks: dict[str, Any] = {}
    for condition in CONDITIONS:
        condition_rows = [row for row in selected if row["condition_id"] == condition]
        if len(condition_rows) != 24 or Counter(row["answer_type"] for row in condition_rows) != Counter({answer_type: 6 for answer_type in ANSWER_TYPES}):
            raise ValueError(f"wrong selected denominator or answer-type allocation: {condition}")
        scored = [score_row(row, cases_by_id[row["case_id"]]) for row in condition_rows]
        slices = {answer_type: metric_summary([row for row in scored if row["answer_type"] == answer_type]) for answer_type in ANSWER_TYPES}
        by_condition[condition] = {"aggregate": metric_summary(scored), "by_answer_type": slices, "case_scores": scored}
        aggregate = by_condition[condition]["aggregate"]
        checks = {
            "case_denominator": aggregate["case_denominator"] == sum(slices[answer_type]["case_denominator"] for answer_type in ANSWER_TYPES),
            "citation_item_denominator": aggregate["citation_item_denominator"] == sum(slices[answer_type]["citation_item_denominator"] for answer_type in ANSWER_TYPES),
            "fatal_gate_count": aggregate["fatal_gate_count"] == sum(slices[answer_type]["fatal_gate_count"] for answer_type in ANSWER_TYPES),
        }
        arithmetic_checks[condition] = {"passed": all(checks.values()), "checks": checks}
    command = "PYTHONPATH=. .venv/bin/python artifacts/reports/20260816T110727Z-4b3a9c40865b/t18_score_c05.py --input artifacts/authoritative-runs/20260816T110727Z-4b3a9c40865b/raw-traces.jsonl --cases eval/v1/development_cases.json --holdout-manifest eval/v1/holdout_manifest.json --output artifacts/reports/20260816T110727Z-4b3a9c40865b/t18-quality-evidence.json"
    report = {
        "task": "T18", "status": "complete_with_cli_follow_up_gap", "generation_command": command,
        "execution_notes": {"initial_command": "python artifacts/reports/20260816T110727Z-4b3a9c40865b/t18_score_c05.py ...", "initial_result": "ModuleNotFoundError: No module named 'scripts'", "successful_command": command, "root_cause": "direct execution from a nested artifact directory does not include repository root on sys.path"},
        "inputs": {"raw_traces": str(args.input), "development_cases": str(args.cases), "holdout_manifest": str(args.holdout_manifest)},
        "method": {"quality_unit": "one saved repetition-0 output per case and condition", "latency_repetitions_not_quality_samples": True, "public_grader_provenance": {"retrieval": "scripts.evaluation.grade_retrieval", "citations": "scripts.evaluation.grade_citations", "text": "scripts.evaluation.grade_text_answer", "trace_validation": "scripts.evaluation.validate_trace"}, "citation_validity_scope": "Cited IDs are checked against trace-resolved retrieved passage IDs; independent corpus-catalog membership is unavailable from C05 trace fields alone.", "unavailable_metrics": ["manual review for ambiguous free-form task resolution", "question/context/output-length quartile slices", "independent pinned-corpus citation membership"]},
        "validation": {"trace_count": len(rows), "selected_quality_row_count": len(selected), "sealed_case_exclusion": {"sealed_case_count": len(sealed_ids), "intersection_count": len(trace_case_ids & sealed_ids), "all_trace_holdout_flags_false": all(row.get("holdout") is False for row in rows)}, "identity_values": identities, "trace_validation_issue_row_count": len(validation_issues), "trace_validation_issues": validation_issues, "repetition_parity": parity(rows), "metric_arithmetic": arithmetic_checks},
        "metrics": by_condition,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
