"""Contract tests for deterministic text-corpus ingestion and retrieval."""

import pytest
import subprocess
import sys
from pathlib import Path
import json

from scripts.ingestion.corpus import ingest_from_materialization, ingest_passages
from scripts.text_rag import (
    TextRagError,
    assemble_context,
    build_index,
    retrieve,
)


def _rows():
    return [
        {"id": 9, "passage": "Zebras live in Africa."},
        {"id": 2, "passage": "The capital of France is Paris."},
        {"id": 7, "passage": "Paris is a city in France with museums."},
    ]


def test_retrieval_has_stable_ranks_and_context_binds_only_admitted_sources():
    manifest = ingest_passages(_rows(), corpus_hash="a" * 64)
    index = build_index(manifest)

    ranked = retrieve(index, "What is the capital of France?", retrieve_k=20)
    context = assemble_context(ranked, admitted_top_k=2, character_budget=200)

    assert [item.evidence_id for item in ranked[:2]] == ["passage:2", "passage:7"]
    assert [item.rank for item in ranked] == list(range(1, len(ranked) + 1))
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


def test_ingestion_cli_runs_directly_from_the_repository_root():
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "-m", "scripts.ingestion.run", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Create the durable text-passage manifest" in result.stdout


def test_retrieval_cli_returns_ranked_and_admitted_evidence(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(ingest_passages(_rows(), corpus_hash="a" * 64)), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/retrieve.py",
            "--manifest",
            str(manifest_path),
            "--question",
            "What is the capital of France?",
            "--character-budget",
            "200",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ranked_evidence_ids"][:2] == ["passage:2", "passage:7"]
    assert payload["admitted_evidence_ids"] == ["passage:2", "passage:7"]
