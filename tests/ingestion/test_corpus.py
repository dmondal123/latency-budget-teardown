"""Focused tests for text-corpus ingestion helpers."""

import pytest

from scripts.ingestion.corpus import ingest_passages, load_cached_passages
from scripts.text_rag import TextRagError


def _rows():
    return [
        {"id": 9, "passage": "Zebras live in Africa."},
        {"id": 2, "passage": "The capital of France is Paris."},
        {"id": 7, "passage": "Paris is a city in France with museums."},
    ]


def test_ingestion_normalizes_sorts_and_creates_a_content_addressed_manifest():
    manifest = ingest_passages(_rows(), corpus_hash="a" * 64)

    assert manifest["schema_version"] == "text-evidence-manifest.v1"
    assert [record["evidence_id"] for record in manifest["passages"]] == ["passage:2", "passage:7", "passage:9"]
    assert manifest["passages"][0]["passage"] == "The capital of France is Paris."
    assert len(manifest["index_snapshot"]) == 64
    assert all(len(record["text_sha256"]) == 64 for record in manifest["passages"])


def test_ingestion_rejects_duplicate_or_malformed_passages():
    with pytest.raises(TextRagError, match="duplicate"):
        ingest_passages([{"id": 1, "passage": "a"}, {"id": 1, "passage": "b"}], corpus_hash="a" * 64)
    with pytest.raises(TextRagError, match="non-empty"):
        ingest_passages([{"id": 1, "passage": "  "}], corpus_hash="a" * 64)
def test_cached_arrow_ingestion_never_uses_a_hub_loader(tmp_path):
    arrow = tmp_path / "rag-datasets___rag-mini-wikipedia" / "text-corpus" / "0.0.0" / "pinned" / "rag-mini-wikipedia-passages.arrow"
    arrow.parent.mkdir(parents=True)
    arrow.touch()
    calls = []

    rows = load_cached_passages(
        tmp_path,
        revision="pinned",
        dataset_from_file=lambda path: calls.append(path) or [{"id": 2, "passage": "cached"}],
    )

    assert rows == ({"id": 2, "passage": "cached"},)
    assert calls == [str(arrow)]
