"""Regression checks for the text-RAG contract and sealed split verifier."""

import json
from pathlib import Path

from scripts.verify_eval import validate_cases


def _case(case_id, source_id, evidence_id, holdout=False):
    return {
        "case_id": case_id, "source_row_id": source_id, "question": "Where?", "reference_answer": "Paris",
        "answer_type": "short_phrase", "gold_evidence_ids": [evidence_id], "support_quote": "Paris is a city",
        "expected_abstention": False, "verification_status": "manually_verified", "holdout": holdout,
    }


def test_text_verifier_rejects_quote_absent_from_declared_passage(tmp_path):
    corpus = [{"id": 42, "passage": "Berlin is a city."}]
    cases = [_case("eval-v1-01", 1, 42)]
    errors = validate_cases(cases, {"case_ids": []}, corpus)
    assert any("support quote" in error for error in errors)


def test_versioned_schema_is_text_rag_case_schema():
    schema = json.loads((Path(__file__).resolve().parents[1] / "eval/v1/case.schema.json").read_text())
    assert schema["title"] == "Text RAG evaluation case v1"
    assert schema["properties"]["gold_evidence_ids"]["items"]["type"] == "integer"
