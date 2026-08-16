"""Deterministic ingestion, BM25 retrieval, and text-context assembly.

This module owns the text-only evidence boundary described in
``RAG_PIPELINE_PLAN.md``.  It deliberately performs no generation or
validation: callers receive durable passage IDs and source labels that those
later stages can validate against.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from rank_bm25 import BM25Okapi


_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")
_MANIFEST_VERSION = "text-evidence-manifest.v1"
_BM25_CONFIG = {"algorithm": "BM25Okapi", "k1": 1.2, "b": 0.75}


class TextRagError(ValueError):
    """Raised when a corpus or retrieval contract is malformed."""


@dataclass(frozen=True)
class Passage:
    evidence_id: str
    passage_id: int
    text: str
    text_sha256: str


@dataclass(frozen=True)
class RetrievedPassage:
    evidence_id: str
    passage_id: int
    text: str
    score: float
    rank: int


@dataclass(frozen=True)
class AssembledContext:
    admitted_evidence_ids: tuple[str, ...]
    text: str
    abstained: bool
    reason: str | None
    input_characters: int


@dataclass(frozen=True)
class BM25Index:
    passages: tuple[Passage, ...]
    corpus_hash: str
    index_snapshot: str
    _index: BM25Okapi


def normalize_text(value: str) -> str:
    """Apply the ingestion normalization shared with dataset materialization."""
    if not isinstance(value, str):
        raise TextRagError(f"passage must be a string, got {type(value).__name__}")
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", value)).strip()


def tokenize(value: str) -> list[str]:
    return _TOKEN_RE.findall(value.casefold())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _validate_hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise TextRagError(f"{field} must be a lowercase SHA-256 hex digest")


def _snapshot(corpus_hash: str, passages: Sequence[Passage]) -> str:
    payload = {
        "schema_version": _MANIFEST_VERSION,
        "corpus_hash": corpus_hash,
        "bm25": _BM25_CONFIG,
        "passages": [
            {"evidence_id": passage.evidence_id, "text_sha256": passage.text_sha256}
            for passage in passages
        ],
    }
    return _sha256_text(_canonical_json(payload))


def ingest_passages(rows: Sequence[Mapping[str, Any]], *, corpus_hash: str) -> dict[str, Any]:
    """Produce a sorted, content-addressed durable manifest from HF corpus rows."""
    _validate_hash(corpus_hash, "corpus_hash")
    passages: list[Passage] = []
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
        passages.append(Passage(f"passage:{passage_id}", passage_id, text, _sha256_text(text)))
    passages.sort(key=lambda passage: passage.passage_id)
    snapshot = _snapshot(corpus_hash, passages)
    return {
        "schema_version": _MANIFEST_VERSION,
        "corpus_hash": corpus_hash,
        "index_snapshot": snapshot,
        "bm25": dict(_BM25_CONFIG),
        "passages": [
            {
                "evidence_id": passage.evidence_id,
                "passage_id": passage.passage_id,
                "passage": passage.text,
                "text_sha256": passage.text_sha256,
            }
            for passage in passages
        ],
    }


def build_index(manifest: Mapping[str, Any]) -> BM25Index:
    """Build the fixed BM25 index and reject manifest/snapshot drift."""
    if manifest.get("schema_version") != _MANIFEST_VERSION:
        raise TextRagError(f"expected {_MANIFEST_VERSION}")
    corpus_hash = manifest.get("corpus_hash")
    _validate_hash(corpus_hash, "corpus_hash")
    raw_passages = manifest.get("passages")
    if not isinstance(raw_passages, list):
        raise TextRagError("manifest passages must be a list")
    passages = tuple(
        Passage(
            evidence_id=str(raw["evidence_id"]),
            passage_id=int(raw["passage_id"]),
            text=normalize_text(raw["passage"]),
            text_sha256=str(raw["text_sha256"]),
        )
        for raw in raw_passages
        if isinstance(raw, Mapping)
    )
    if len(passages) != len(raw_passages) or len({passage.passage_id for passage in passages}) != len(passages):
        raise TextRagError("manifest passages must be unique objects")
    if tuple(sorted(passages, key=lambda passage: passage.passage_id)) != passages:
        raise TextRagError("manifest passages must be sorted by passage_id")
    for passage in passages:
        if passage.evidence_id != f"passage:{passage.passage_id}" or passage.text_sha256 != _sha256_text(passage.text):
            raise TextRagError(f"invalid durable metadata for {passage.evidence_id}")
    expected_snapshot = _snapshot(corpus_hash, passages)
    if manifest.get("index_snapshot") != expected_snapshot:
        raise TextRagError("manifest index_snapshot does not match passages")
    tokens = [tokenize(passage.text) for passage in passages]
    return BM25Index(passages, corpus_hash, expected_snapshot, BM25Okapi(tokens, k1=1.2, b=0.75))


def retrieve(index: BM25Index, query: str, *, retrieve_k: int = 20) -> tuple[RetrievedPassage, ...]:
    """Return positive BM25 matches in score/id order with stable one-based ranks."""
    if retrieve_k < 0:
        raise TextRagError("retrieve_k must be non-negative")
    query_tokens = tokenize(normalize_text(query))
    if not query_tokens or not index.passages or retrieve_k == 0:
        return ()
    scores = index._index.get_scores(query_tokens)
    scored = [
        (float(score), passage)
        for score, passage in zip(scores, index.passages)
        if score > 0
    ]
    scored.sort(key=lambda pair: (-pair[0], pair[1].passage_id))
    return tuple(
        RetrievedPassage(passage.evidence_id, passage.passage_id, passage.text, score, rank)
        for rank, (score, passage) in enumerate(scored[:retrieve_k], 1)
    )


def assemble_context(
    ranked: Sequence[RetrievedPassage], *, admitted_top_k: int = 5, character_budget: int = 12_000
) -> AssembledContext:
    """Pack rank-ordered whole passages, binding labels only after admission."""
    if admitted_top_k < 0 or character_budget < 0:
        raise TextRagError("context budgets must be non-negative")
    sections: list[str] = []
    evidence_ids: list[str] = []
    for item in ranked:
        if len(evidence_ids) >= admitted_top_k:
            break
        label = f"SOURCE_{len(evidence_ids) + 1}"
        section = f"{label} [{item.evidence_id}]\n{item.text}"
        next_length = sum(len(part) for part in sections) + (2 * len(sections)) + len(section)
        if next_length > character_budget:
            continue
        sections.append(section)
        evidence_ids.append(item.evidence_id)
    if not sections:
        return AssembledContext((), "", True, "zero_admissible_evidence", 0)
    text = "\n\n".join(sections)
    return AssembledContext(tuple(evidence_ids), text, False, None, len(text))
