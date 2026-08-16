#!/usr/bin/env python3
"""Create the durable text-passage manifest from the pinned HF cache."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from scripts.materialize_dataset import (
    DATASET_REVISION,
    MaterializationError,
)
from scripts.text_rag import TextRagError, ingest_passages


def ingest_from_materialization(
    rows: Sequence[Mapping[str, Any]], materialization: Mapping[str, Any]
) -> dict[str, Any]:
    """Bind ingested passages to the successful pinned text-corpus record."""
    configurations = materialization.get("configurations")
    if not isinstance(configurations, list):
        raise TextRagError("dataset materialization configurations must be a list")
    record = next(
        (
            candidate
            for candidate in configurations
            if isinstance(candidate, Mapping)
            and candidate.get("config") == "text-corpus"
            and candidate.get("split") == "passages"
        ),
        None,
    )
    if not isinstance(record, Mapping) or record.get("status") != "materialized":
        raise TextRagError("pinned text-corpus is not materialized")
    corpus_hash = record.get("normalized_corpus_sha256")
    manifest = ingest_passages(rows, corpus_hash=str(corpus_hash))
    dataset = materialization.get("dataset")
    if not isinstance(dataset, Mapping):
        raise TextRagError("dataset materialization is missing dataset identity")
    return {**manifest, "dataset": dict(dataset)}


def load_cached_passages(
    cache_root: Path,
    *,
    revision: str = DATASET_REVISION,
    dataset_from_file: Callable[[str], Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Load exactly one materialized Arrow file without contacting the Hub."""
    candidates = sorted(
        path for path in cache_root.rglob("rag-mini-wikipedia-passages.arrow") if revision in path.parts
    )
    if len(candidates) != 1:
        raise TextRagError(f"expected one cached passages Arrow file at revision {revision}, found {len(candidates)}")
    if dataset_from_file is None:
        try:
            from datasets import Dataset
        except ImportError as exc:
            raise TextRagError("datasets tooling is unavailable; install requirements.txt") from exc
        dataset_from_file = Dataset.from_file
    dataset = dataset_from_file(str(candidates[0]))
    rows = tuple(dict(row) for row in dataset)
    if not rows or any(set(row) != {"id", "passage"} for row in rows):
        raise TextRagError("cached passages Arrow file has an unexpected schema")
    return rows


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TextRagError("dataset materialization must be an object")
    return value


def write_manifest(manifest: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=Path(os.environ.get("T09_DATASET_CACHE", Path.home() / ".cache" / "week-1-fde" / "datasets")))
    parser.add_argument("--dataset-manifest", type=Path, default=repo_root / "artifacts/dataset_materialization.v1.json")
    parser.add_argument("--output", type=Path, default=repo_root / "artifacts/text_evidence_manifest.v1.json")
    args = parser.parse_args(argv)
    try:
        materialization = load_json(args.dataset_manifest)
        rows = load_cached_passages(args.cache_root / "text-corpus")
        manifest = ingest_from_materialization(rows, materialization)
        write_manifest(manifest, args.output)
    except (MaterializationError, TextRagError, OSError, json.JSONDecodeError) as exc:
        print(f"ingestion blocked: {exc}", file=sys.stderr)
        return 2
    print(f"ingested {len(manifest['passages'])} passages: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
