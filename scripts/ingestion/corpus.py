"""Create the durable text-passage manifest from the pinned HF cache."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .materialize import DATASET_REVISION

_MANIFEST_VERSION = "text-evidence-manifest.v1"
_BM25_CONFIG = {"algorithm": "BM25Okapi", "k1": 1.2, "b": 0.75}
_WHITESPACE_RE = re.compile(r"\s+")


class TextRagError(ValueError):
    """Raised when a corpus or retrieval contract is malformed."""


def normalize_text(value: str) -> str:
    """Apply the ingestion normalization shared with dataset materialization."""
    if not isinstance(value, str):
        raise TextRagError(f"passage must be a string, got {type(value).__name__}")
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", value)).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _validate_hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise TextRagError(f"{field} must be a lowercase SHA-256 hex digest")


def _snapshot(corpus_hash: str, passages: Sequence[dict[str, Any]]) -> str:
    payload = {
        "schema_version": _MANIFEST_VERSION,
        "corpus_hash": corpus_hash,
        "bm25": _BM25_CONFIG,
        "passages": [
            {"evidence_id": passage["evidence_id"], "text_sha256": passage["text_sha256"]}
            for passage in passages
        ],
    }
    return _sha256_text(_canonical_json(payload))


def ingest_passages(rows: Sequence[Mapping[str, Any]], *, corpus_hash: str) -> dict[str, Any]:
    """Produce a sorted, content-addressed durable manifest from HF corpus rows."""
    _validate_hash(corpus_hash, "corpus_hash")
    passages: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for number, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TextRagError(f"row {number} must be an object")
        passage_id = row.get("id")
        if isinstance(passage_id, bool) or not isinstance(passage_id, int):
            raise TextRagError(f"row {number} id must be an integer")
        if passage_id in seen_ids:
            raise TextRagError(f"duplicate passage id: {passage_id}")
        seen_ids.add(passage_id)
        text = normalize_text(row.get("passage"))
        if not text:
            raise TextRagError(f"row {number} passage must be non-empty")
        passages.append(
            {
                "evidence_id": f"passage:{passage_id}",
                "passage_id": passage_id,
                "passage": text,
                "text_sha256": _sha256_text(text),
            }
        )
    passages.sort(key=lambda passage: int(passage["passage_id"]))
    snapshot = _snapshot(corpus_hash, passages)
    return {
        "schema_version": _MANIFEST_VERSION,
        "corpus_hash": corpus_hash,
        "index_snapshot": snapshot,
        "bm25": dict(_BM25_CONFIG),
        "passages": passages,
    }


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
