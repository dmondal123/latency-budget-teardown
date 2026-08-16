"""Deterministic text-passage retrieval and bounded prompt assembly."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from scripts.materialize_dataset import normalize_text

TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
INDEX_PARAMETERS = {"algorithm": "bm25", "k1": 1.2, "b": 0.75, "tokenizer": "unicode_word_v1"}


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(match.group(0).casefold() for match in TOKEN_RE.finditer(value))


@dataclass(frozen=True)
class Passage:
    id: int
    text: str


@dataclass(frozen=True)
class RetrievalHit:
    passage: Passage
    score: float
    rank: int


@dataclass(frozen=True)
class Context:
    passages: tuple[Passage, ...]
    bindings: dict[str, int]
    prompt: str
    abstained: bool
    reason: str | None = None

    @property
    def admitted_ids(self) -> tuple[int, ...]:
        return tuple(passage.id for passage in self.passages)


def canonical_passages(rows: Iterable[Mapping[str, object]]) -> tuple[Passage, ...]:
    passages: list[Passage] = []
    for number, row in enumerate(rows):
        identifier = row.get("id")
        text = row.get("passage")
        if isinstance(identifier, bool) or not isinstance(identifier, int):
            raise ValueError(f"passage {number} id must be an integer")
        if not isinstance(text, str):
            raise ValueError(f"passage {number} must be a string")
        normalized = normalize_text(text)
        if not normalized:
            raise ValueError(f"passage {number} must be non-empty")
        passages.append(Passage(identifier, normalized))
    passages.sort(key=lambda passage: passage.id)
    if len({passage.id for passage in passages}) != len(passages):
        raise ValueError("duplicate passage IDs")
    return tuple(passages)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class PassageIndex:
    """A deterministic in-memory BM25 index over normalized passages."""

    def __init__(self, rows: Iterable[Mapping[str, object]], *, k1: float = 1.2, b: float = 0.75) -> None:
        if k1 < 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 >= 0 and 0 <= b <= 1")
        self.passages = canonical_passages(rows)
        self.k1, self.b = k1, b
        self._terms = tuple(_tokens(passage.text) for passage in self.passages)
        self._average_length = sum(map(len, self._terms)) / len(self._terms) if self._terms else 0.0
        frequencies = Counter(term for terms in self._terms for term in set(terms))
        total = len(self.passages)
        self._idf = {term: math.log(1 + (total - frequency + 0.5) / (frequency + 0.5)) for term, frequency in frequencies.items()}
        canonical = [{"id": passage.id, "passage": passage.text} for passage in self.passages]
        self.corpus_hash = _digest(canonical)
        self.snapshot_hash = _digest({"corpus_hash": self.corpus_hash, **INDEX_PARAMETERS, "k1": k1, "b": b})

    def search(self, query: str, *, limit: int = 20) -> tuple[RetrievalHit, ...]:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        query_terms = set(_tokens(normalize_text(query)))
        hits: list[RetrievalHit] = []
        for passage, terms in zip(self.passages, self._terms):
            counts = Counter(terms)
            score = 0.0
            for term in query_terms:
                if term not in counts:
                    continue
                denominator = counts[term] + self.k1 * (1 - self.b + self.b * len(terms) / self._average_length)
                score += self._idf[term] * counts[term] * (self.k1 + 1) / denominator
            if score:
                hits.append(RetrievalHit(passage, score, 0))
        hits.sort(key=lambda hit: (-hit.score, hit.passage.id))
        return tuple(RetrievalHit(hit.passage, hit.score, rank) for rank, hit in enumerate(hits[:limit], 1))


def assemble_context(
    hits: Sequence[RetrievalHit], *, max_passages: int = 5, max_characters: int = 12_000, max_tokens: int = 2_000
) -> Context:
    if min(max_passages, max_characters, max_tokens) < 0:
        raise ValueError("context limits must be non-negative")
    admitted: list[Passage] = []
    characters = tokens = 0
    for hit in hits:
        passage = hit.passage
        passage_tokens = len(_tokens(passage.text))
        if len(admitted) >= max_passages:
            break
        if characters + len(passage.text) > max_characters or tokens + passage_tokens > max_tokens:
            continue
        admitted.append(passage)
        characters += len(passage.text)
        tokens += passage_tokens
    if not admitted:
        return Context((), {}, "", True, "zero_admissible_evidence")
    bindings = {f"SOURCE_{number}": passage.id for number, passage in enumerate(admitted, 1)}
    prompt = "\n\n".join(f"{label}\n{passage.text}" for label, passage in zip(bindings, admitted))
    return Context(tuple(admitted), bindings, prompt, False)


def resolve_citations(citations: Sequence[str], bindings: Mapping[str, int]) -> tuple[int, ...]:
    resolved: list[int] = []
    for citation in citations:
        if citation not in bindings:
            raise ValueError(f"citation is outside admitted context: {citation}")
        resolved.append(bindings[citation])
    return tuple(resolved)
