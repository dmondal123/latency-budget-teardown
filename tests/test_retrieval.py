"""Text-RAG retrieval and context contracts.

Each assertion here catches a user-visible contract break: ordering, bounded
admission, or citations escaping the admitted context.
"""

import pytest

from scripts.retrieval import (
    Passage,
    PassageIndex,
    assemble_context,
    canonical_passages,
    resolve_citations,
)


def _rows():
    return [
        {"id": 9, "passage": "Latency budgets keep responses predictable."},
        {"id": 2, "passage": "BM25 retrieval ranks matching passages."},
        {"id": 7, "passage": "A citation must name admitted evidence."},
    ]


def test_canonical_passages_normalize_and_order_by_durable_id():
    passages = canonical_passages(list(reversed(_rows())))
    assert [(item.id, item.text) for item in passages] == [
        (2, "BM25 retrieval ranks matching passages."),
        (7, "A citation must name admitted evidence."),
        (9, "Latency budgets keep responses predictable."),
    ]


def test_index_identity_and_rank_are_stable_when_input_order_changes():
    first = PassageIndex(_rows())
    second = PassageIndex(list(reversed(_rows())))
    assert first.corpus_hash == second.corpus_hash
    assert first.snapshot_hash == second.snapshot_hash
    assert [hit.passage.id for hit in first.search("BM25 retrieval", limit=20)] == [2]


def test_context_binds_only_admitted_passages_in_rank_order():
    index = PassageIndex(_rows())
    context = assemble_context(
        index.search("citation latency", limit=20), max_passages=2, max_characters=200, max_tokens=30
    )
    assert context.admitted_ids == (9, 7)
    assert context.bindings == {"SOURCE_1": 9, "SOURCE_2": 7}
    assert "SOURCE_1" in context.prompt and "SOURCE_2" in context.prompt
    assert resolve_citations(["SOURCE_2"], context.bindings) == (7,)
    with pytest.raises(ValueError, match="outside admitted context"):
        resolve_citations(["SOURCE_3"], context.bindings)


def test_context_abstains_without_admissible_evidence():
    context = assemble_context((), max_passages=5, max_characters=100, max_tokens=20)
    assert context.abstained is True
    assert context.reason == "zero_admissible_evidence"


def test_invalid_and_duplicate_passage_ids_fail_before_indexing():
    with pytest.raises(ValueError, match="duplicate"):
        canonical_passages([{"id": 1, "passage": "a"}, {"id": 1, "passage": "b"}])
    with pytest.raises(ValueError, match="non-empty"):
        canonical_passages([{"id": 1, "passage": " \t "}])
