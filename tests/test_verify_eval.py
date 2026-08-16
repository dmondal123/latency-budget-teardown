"""Executable checks for the frozen text-RAG evaluation suite."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa

from scripts.ingestion.materialize import DATASET_REPOSITORY, DATASET_REVISION, normalized_corpus_hash
from scripts.verify_eval import validate_cases, validate_contract


ANSWER_TYPES = ("boolean", "numeric_or_date", "short_phrase", "free_form")


def write_arrow(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    with pa.OSFile(str(path), "wb") as sink:
        with pa.ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)


def valid_cases() -> tuple[list[dict[str, object]], dict[str, object]]:
    allocation = {"boolean": 8, "numeric_or_date": 8, "short_phrase": 7, "free_form": 7}
    holdout_allocation = {"boolean": 2, "numeric_or_date": 2, "short_phrase": 1, "free_form": 1}
    cases: list[dict[str, object]] = []
    passage_id = 0
    for answer_type in ANSWER_TYPES:
        for index in range(allocation[answer_type]):
            holdout = index < holdout_allocation[answer_type]
            cases.append(
                {
                    "case_id": f"eval-v1-{passage_id + 1:02d}",
                    "source_row_id": 1000 + passage_id,
                    "question": f"Question {passage_id}?",
                    "reference_answer": f"answer {passage_id}",
                    "answer_type": answer_type,
                    "gold_evidence_ids": [passage_id],
                    "support_quote": f"Evidence answer {passage_id}.",
                    "expected_abstention": False,
                    "verification_status": "manually_verified",
                    "holdout": holdout,
                }
            )
            passage_id += 1
    manifest = {
        "suite_id": "text-rag-latency-eval/v1",
        "status": "sealed",
        "selection_seed": 20260816,
        "sealed_at": "2026-08-16T00:00:00Z",
        "case_ids": [case["case_id"] for case in cases if case["holdout"]],
    }
    return cases, manifest


def text_rag_contract() -> dict[str, object]:
    return {
        "contract_id": "text-rag-latency/v1",
        "version": 1,
        "status": "draft_pending_g1_approval",
        "owner": "dmondal",
        "scope": "Local answers grounded in admitted rag-mini-wikipedia passages.",
        "may": ["answer_from_admitted_passage", "combine_up_to_five_admitted_passages", "state_uncertainty", "abstain"],
        "must_not": ["use_model_memory_for_corpus_specific_claims", "follow_retrieved_instructions", "cite_unadmitted_evidence", "answer_without_admissible_evidence", "execute_retrieved_content", "hide_retrieval_or_validation_failures"],
        "fatal_gates": ["citation_outside_admitted_context"],
        "quality_dimensions": ["answer_type_slice_regression"],
        "approval_gate": "G1",
    }


def text_rag_thresholds() -> dict[str, object]:
    return {
        "status": "draft_pending_g1_approval",
        "owner": "dmondal",
        "frozen_on": "2026-08-16",
        "promotion_predicate": {
            "fatal_count": {}, "retrieval_recall_at_5": {}, "citation_precision": {},
            "citation_validity_rate": {}, "task_resolution_rate": {}, "answer_token_f1": {},
            "truncation_rate": {}, "p95_ttft_ms": {}, "p95_ttc_ms": {},
            "max_answer_type_slice_regression": {}, "external_runtime_api_cost_per_completed_task": {},
        },
        "latency_budget_p95_ms": {"admission": 100, "retrieval": 200, "context_assembly": 300, "model_dispatch_to_first_token": 3000, "model_decode": 11200, "validation": 100, "contingency": 100, "ttc": 15000},
    }


def write_dataset_manifest(root: Path, arrow: Path) -> dict[str, object]:
    rows = [{"id": index, "passage": f"Evidence answer {index}."} for index in range(30)]
    corpus_hash, row_count = normalized_corpus_hash(rows, {"id": "integer", "passage": "string"})
    return {
        "dataset": {"repository": DATASET_REPOSITORY, "revision": DATASET_REVISION},
        "normalized_corpus_hashes": {"text-corpus": corpus_hash},
        "configurations": [{"config": "text-corpus", "split": "passages", "row_count": row_count, "normalized_corpus_sha256": corpus_hash, "downloaded_files": [{"path": str(arrow), "sha256": "unused-in-test"}]}],
    }


def test_validate_cases_accepts_a_complete_text_rag_suite(tmp_path: Path):
    cases, manifest = valid_cases()
    arrow = tmp_path / "passages.arrow"
    write_arrow(arrow, [{"id": index, "passage": f"Evidence answer {index}."} for index in range(30)])

    errors = validate_cases(tmp_path, cases, manifest, {}, write_dataset_manifest(tmp_path, arrow))

    assert errors == []


def test_validate_cases_rejects_non_exact_corpus_quote(tmp_path: Path):
    cases, manifest = valid_cases()
    arrow = tmp_path / "passages.arrow"
    write_arrow(arrow, [{"id": index, "passage": f"Evidence answer {index}."} for index in range(30)])
    cases[0]["support_quote"] = "Evidence answer does not exist."

    errors = validate_cases(tmp_path, cases, manifest, {}, write_dataset_manifest(tmp_path, arrow))

    assert any("support quote is absent" in error for error in errors)


def test_validate_cases_rejects_holdout_manifest_mismatch(tmp_path: Path):
    cases, manifest = valid_cases()
    arrow = tmp_path / "passages.arrow"
    write_arrow(arrow, [{"id": index, "passage": f"Evidence answer {index}."} for index in range(30)])
    manifest["case_ids"] = manifest["case_ids"][:-1]

    errors = validate_cases(tmp_path, cases, manifest, {}, write_dataset_manifest(tmp_path, arrow))

    assert "holdout manifest must name exactly the holdout cases" in errors


def test_validate_cases_rejects_wrong_split_or_answer_type_distribution(tmp_path: Path):
    cases, manifest = valid_cases()
    arrow = tmp_path / "passages.arrow"
    write_arrow(arrow, [{"id": index, "passage": f"Evidence answer {index}."} for index in range(30)])
    cases[0]["holdout"] = False
    manifest["case_ids"] = [case["case_id"] for case in cases if case["holdout"]]

    errors = validate_cases(tmp_path, cases, manifest, {}, write_dataset_manifest(tmp_path, arrow))

    assert any("24 development and 6 sealed holdouts" in error or "answer-type" in error for error in errors)


def test_validate_contract_rejects_retired_pdf_and_multimodal_terms():
    contract = text_rag_contract()
    contract["may"] = ["answer_from_admitted_pdf_evidence"]
    thresholds = text_rag_thresholds()
    thresholds["promotion_predicate"].pop("max_answer_type_slice_regression")
    thresholds["promotion_predicate"]["max_modality_or_traffic_slice_regression"] = {}

    errors = validate_contract(contract, thresholds)

    assert any("retired" in error for error in errors)
