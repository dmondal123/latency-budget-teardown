"""Deterministic text-evaluation selection contracts."""

from scripts.prepare_eval import classify_answer, materialize_cases, select_candidates


def test_selection_is_seeded_and_never_uses_a_qa_id_as_passage_id():
    qa = [
        {"id": 101, "question": "q1", "answer": "yes"},
        {"id": 102, "question": "q2", "answer": "42"},
        {"id": 103, "question": "q3", "answer": "Paris"},
        {"id": 104, "question": "q4", "answer": "a longer answer"},
    ]
    corpus = [{"id": 1, "passage": "The answer is yes."}, {"id": 2, "passage": "The value is 42."}, {"id": 3, "passage": "Paris is a city."}, {"id": 4, "passage": "A longer answer has several words."}]
    first = select_candidates(qa, corpus, seed=20260816)
    second = select_candidates(list(reversed(qa)), corpus, seed=20260816)
    assert first == second
    assert [item["candidate_passage_ids"] for item in first] == [[1], [2], [3], [4]]
    assert all(item["source_row_id"] not in item["candidate_passage_ids"] for item in first)


def test_answer_classification_uses_the_four_frozen_types():
    assert classify_answer("yes") == "boolean"
    assert classify_answer("2026-08-16") == "numeric_or_date"
    assert classify_answer("Paris") == "short_phrase"
    assert classify_answer("a sentence with many distinct words") == "free_form"


def test_materializer_seals_a_deterministic_24_6_split_from_approved_rows():
    approved = [
        {"source_row_id": index, "question": f"q{index}", "reference_answer": "yes", "answer_type": "boolean",
         "gold_evidence_ids": [index + 100], "support_quote": "yes"}
        for index in range(30)
    ]
    development, holdouts, manifest = materialize_cases(approved, seed=20260816, sealed_at="2026-08-16T00:00:00Z")
    assert len(development) == 24
    assert len(holdouts) == 6
    assert {case["case_id"] for case in holdouts} == set(manifest["case_ids"])
    assert all(case["verification_status"] == "manually_verified" for case in development + holdouts)
