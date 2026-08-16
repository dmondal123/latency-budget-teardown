"""Contract tests for deterministic text-context admission."""

from scripts.ingestion.corpus import ingest_passages
from scripts.retrieval import assemble_context, build_index, retrieve


def _rows():
    return [
        {"id": 9, "passage": "Zebras live in Africa."},
        {"id": 2, "passage": "The capital of France is Paris."},
        {"id": 7, "passage": "Paris is a city in France with museums."},
    ]


def test_context_binds_only_admitted_sources():
    manifest = ingest_passages(_rows(), corpus_hash="a" * 64)
    ranked = retrieve(build_index(manifest), "What is the capital of France?", retrieve_k=20)

    context = assemble_context(ranked, admitted_top_k=2, character_budget=200)

    assert context.abstained is False
    assert context.admitted_evidence_ids == ("passage:2", "passage:7")
    assert "SOURCE_1 [passage:2]" in context.text
    assert "SOURCE_2 [passage:7]" in context.text


def test_context_admission_skips_over_budget_passages_and_abstains_when_none_fit():
    manifest = ingest_passages(_rows(), corpus_hash="a" * 64)
    ranked = retrieve(build_index(manifest), "France", retrieve_k=20)

    context = assemble_context(ranked, admitted_top_k=5, character_budget=10)

    assert context.abstained is True
    assert context.reason == "zero_admissible_evidence"
    assert context.text == ""
