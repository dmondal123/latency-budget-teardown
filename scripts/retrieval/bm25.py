"""Deterministic BM25 retrieval over durable text evidence manifests."""

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


class RetrievalError(ValueError):
    """Raised when a retrieval manifest or query contract is malformed."""


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
class BM25Index:
    passages: tuple[Passage, ...]
    corpus_hash: str
    index_snapshot: str
    _index: BM25Okapi


def normalize_text(value: str) -> str:
    if not isinstance(value, str):
        raise RetrievalError(f"passage must be a string, got {type(value).__name__}")
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFKC", value)).strip()


def tokenize(value: str) -> list[str]:
    return _TOKEN_RE.findall(value.casefold())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _validate_hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RetrievalError(f"{field} must be a lowercase SHA-256 hex digest")


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


def build_index(manifest: Mapping[str, Any]) -> BM25Index:
    """Build the fixed BM25 index and reject manifest/snapshot drift."""
    if manifest.get("schema_version") != _MANIFEST_VERSION:
        raise RetrievalError(f"expected {_MANIFEST_VERSION}")
    corpus_hash = manifest.get("corpus_hash")
    _validate_hash(corpus_hash, "corpus_hash")
    raw_passages = manifest.get("passages")
    if not isinstance(raw_passages, list):
        raise RetrievalError("manifest passages must be a list")
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
        raise RetrievalError("manifest passages must be unique objects")
    if tuple(sorted(passages, key=lambda passage: passage.passage_id)) != passages:
        raise RetrievalError("manifest passages must be sorted by passage_id")
    for passage in passages:
        if passage.evidence_id != f"passage:{passage.passage_id}" or passage.text_sha256 != _sha256_text(passage.text):
            raise RetrievalError(f"invalid durable metadata for {passage.evidence_id}")
    expected_snapshot = _snapshot(corpus_hash, passages)
    if manifest.get("index_snapshot") != expected_snapshot:
        raise RetrievalError("manifest index_snapshot does not match passages")
    tokens = [tokenize(passage.text) for passage in passages]
    return BM25Index(passages, corpus_hash, expected_snapshot, BM25Okapi(tokens, k1=1.2, b=0.75))


def retrieve(index: BM25Index, query: str, *, retrieve_k: int = 20) -> tuple[RetrievedPassage, ...]:
    """Return positive BM25 matches in score/id order with stable one-based ranks."""
    if retrieve_k < 0:
        raise RetrievalError("retrieve_k must be non-negative")
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
