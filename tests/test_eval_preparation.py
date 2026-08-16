"""Deterministic text-evaluation selection contracts."""

from collections import Counter
import json

import pyarrow as pa

from scripts.prepare_eval import choose_support_mappings, classify_answer, load_arrow_rows, materialize_cases, select_candidates, write_candidate_ledger


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
    assert all(item["disposition"] == "pending_manual_review" for item in first)


def test_selection_marks_overbroad_answer_containment_as_ambiguous():
    qa = [{"id": 1, "question": "How many?", "answer": "1"}]
    corpus = [{"id": index, "passage": f"item 1 number {index}"} for index in range(12)]
    candidate = select_candidates(qa, corpus, seed=20260816, max_candidates=10)[0]
    assert candidate["disposition"] == "rejected_ambiguous"
    assert candidate["candidate_count"] == 12


def test_answer_classification_uses_the_four_frozen_types():
    assert classify_answer("yes") == "boolean"
    assert classify_answer("2026-08-16") == "numeric_or_date"
    assert classify_answer("Paris") == "short_phrase"
    assert classify_answer("a sentence with many distinct words") == "free_form"


def test_materializer_seals_a_deterministic_24_6_split_from_approved_rows():
    types = ["boolean"] * 8 + ["numeric_or_date"] * 8 + ["short_phrase"] * 7 + ["free_form"] * 7
    approved = [{"source_row_id": index, "question": f"q{index}", "reference_answer": "yes", "answer_type": kind,
                 "gold_evidence_ids": [index + 100], "support_quote": "yes"} for index, kind in enumerate(types)]
    development, holdouts, manifest = materialize_cases(approved, seed=20260816, sealed_at="2026-08-16T00:00:00Z")
    assert len(development) == 24
    assert len(holdouts) == 6
    assert {case["case_id"] for case in holdouts} == set(manifest["case_ids"])
    assert Counter(case["answer_type"] for case in holdouts) == {"boolean": 2, "numeric_or_date": 2, "short_phrase": 1, "free_form": 1}
    assert Counter(case["answer_type"] for case in development) == {"boolean": 6, "numeric_or_date": 6, "short_phrase": 6, "free_form": 6}
    assert all(case["verification_status"] == "manually_verified" for case in development + holdouts)


def test_offline_arrow_loader_and_ledger_writer_do_not_need_a_dataset_service(tmp_path):
    arrow = tmp_path / "rows.arrow"
    with pa.OSFile(str(arrow), "wb") as sink:
        with pa.ipc.new_stream(sink, pa.table({"id": [1], "passage": ["Paris"]}).schema) as writer:
            writer.write_table(pa.table({"id": [1], "passage": ["Paris"]}))
    assert load_arrow_rows(arrow) == [{"id": 1, "passage": "Paris"}]
    ledger = tmp_path / "ledger.json"
    write_candidate_ledger(ledger, [{"source_row_id": 9, "candidate_passage_ids": [1]}])
    assert json.loads(ledger.read_text())["candidates"][0]["candidate_passage_ids"] == [1]


def test_support_selector_returns_an_exact_quote_from_a_candidate_passage():
    proposal = choose_support_mappings(
        [{"source_row_id": 1, "question": "Where is Paris?", "reference_answer": "Paris", "candidate_passage_ids": [2]}],
        [{"id": 2, "passage": "Paris is the capital of France. It is in Europe."}],
    )[0]
    assert proposal["gold_evidence_ids"] == [2]
    assert proposal["support_quote"] == "Paris is the capital of France."
