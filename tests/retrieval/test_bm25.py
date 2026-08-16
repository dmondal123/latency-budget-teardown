"""Contract tests for deterministic text-manifest retrieval ranking."""

import pytest

from scripts.ingestion.corpus import TextRagError, ingest_from_materialization, ingest_passages
from scripts.retrieval import build_index, retrieve


def _rows():
    return [
        {"id": 9, "passage": "Zebras live in Africa."},
        {"id": 2, "passage": "The capital of France is Paris."},
        {"id": 7, "passage": "Paris is a city in France with museums."},
    ]


def test_retrieval_has_stable_ranks():
    manifest = ingest_passages(_rows(), corpus_hash="a" * 64)
    index = build_index(manifest)

    ranked = retrieve(index, "What is the capital of France?", retrieve_k=20)

    assert [item.evidence_id for item in ranked[:2]] == ["passage:2", "passage:7"]
    assert [item.rank for item in ranked] == list(range(1, len(ranked) + 1))


def test_ingestion_uses_only_the_pinned_materialized_text_corpus_identity():
    materialization = {
        "dataset": {"repository": "rag-datasets/rag-mini-wikipedia", "revision": "pinned"},
        "configurations": [
            {
                "config": "text-corpus",
                "split": "passages",
                "status": "materialized",
                "normalized_corpus_sha256": "b" * 64,
            }
        ],
    }

    manifest = ingest_from_materialization(_rows(), materialization)

    assert manifest["dataset"] == materialization["dataset"]
    assert manifest["corpus_hash"] == "b" * 64
    with pytest.raises(TextRagError, match="not materialized"):
        ingest_from_materialization(_rows(), {"dataset": {}, "configurations": []})
