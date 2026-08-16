"""CLI contract tests for text-only retrieval package entrypoints."""

import json
import subprocess
import sys
from pathlib import Path

from scripts.ingestion.corpus import ingest_passages


def _rows():
    return [
        {"id": 9, "passage": "Zebras live in Africa."},
        {"id": 2, "passage": "The capital of France is Paris."},
        {"id": 7, "passage": "Paris is a city in France with museums."},
    ]


def test_ingestion_cli_runs_directly_from_the_repository_root():
    repo_root = Path(__file__).resolve().parents[2]

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
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(ingest_passages(_rows(), corpus_hash="a" * 64)), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.retrieval.run",
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
