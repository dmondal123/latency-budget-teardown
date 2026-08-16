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


def test_retired_top_level_text_rag_paths_are_absent():
    repo_root = Path(__file__).resolve().parents[2]
    retired_names = ("ingest_corpus", "retrieve", "text_rag")
    retired_paths = tuple(repo_root / "scripts" / f"{name}.py" for name in retired_names)

    for path in retired_paths:
        assert not path.exists()

    package_layout_plan = (
        repo_root / "docs" / "superpowers" / "plans" / "2026-08-16-text-rag-package-layout.md"
    )
    plan_text = package_layout_plan.read_text(encoding="utf-8")
    for name in retired_names:
        assert f"scripts/{name}.py" not in plan_text
