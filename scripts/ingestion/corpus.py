"""Create the durable text-passage manifest from the pinned HF cache."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from scripts.text_rag import TextRagError, ingest_passages

from .materialize import DATASET_REVISION


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
