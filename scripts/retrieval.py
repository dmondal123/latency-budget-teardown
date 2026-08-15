#!/usr/bin/env python3
"""Deterministic retrieval and bounded context assembly for page evidence.

The module consumes the ``evidence-manifest.v1`` shape produced by
``scripts/ingest_pdfs.py``.  PDF content is data: it is never interpreted as
instructions by this layer.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Mapping, Sequence


TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


@dataclass(frozen=True)
class Evidence:
    """A page-level evidence unit with optional render and visual metadata."""

    evidence_id: str
    document_name: str
    document_sha256: str
    page: int
    text: str
    source: Mapping[str, Any]
    text_sha256: str = ""
    render_sha256: str = ""
    visual_description: str = ""
    page_title: str = ""
    adjacent_metadata: str = ""
    image_width: int = 0
    image_height: int = 0
    expanded_metadata: Mapping[str, Any] = field(default_factory=dict)  # populated only during packing

    @property
    def index_text(self) -> str:
        return " ".join(
            part for part in (self.text, self.visual_description) if part
        )

    @property
    def pixels(self) -> int:
        return max(0, self.image_width) * max(0, self.image_height)

    def __getitem__(self, key: str) -> Any:
        if key == "token_count":
            return len(_tokens(self.text)) + len(_tokens(self.visual_description))
        if key == "image_count":
            return 1 if self.pixels else 0
        if key == "pixel_count":
            return self.pixels
        if key == "expanded_metadata":
            return dict(self.expanded_metadata) if isinstance(self.expanded_metadata, Mapping) else {}
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)


@dataclass(frozen=True)
class RetrievedEvidence:
    evidence: Evidence
    score: float
    rank: int


@dataclass(frozen=True)
class CitationBinding:
    citation: str
    evidence_id: str
    source: Mapping[str, Any]


@dataclass(frozen=True)
class Context:
    evidence: tuple[Evidence, ...]
    citations: tuple[CitationBinding, ...]
    text: str
    abstained: bool
    reason: str | None = None

    def __getitem__(self, key: str) -> Any:
        if key == "evidence":
            return list(self.evidence)
        if key == "abstain":
            return self.abstained
        if key == "reason":
            return self.reason
        raise KeyError(key)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Context):
            return (self.evidence, self.citations, self.text, self.abstained, self.reason) == (other.evidence, other.citations, other.text, other.abstained, other.reason)
        if isinstance(other, Mapping):
            return self["evidence"] == other.get("evidence") and self.abstained == other.get("abstain")
        return super().__eq__(other)


Reranker = Callable[[str, Sequence[RetrievedEvidence]], Sequence[RetrievedEvidence]]


def noop_reranker(_query: str, candidates: Sequence[RetrievedEvidence]) -> Sequence[RetrievedEvidence]:
    """Baseline reranker seam: preserve first-stage order and scores."""
    return candidates


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(TOKEN_RE.findall(text.casefold()))


def _stable_key(item: Evidence) -> tuple[str, int, str]:
    return (item.document_name.casefold(), item.page, item.evidence_id)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evidence_from_manifest(manifest: Mapping[str, Any]) -> tuple[Evidence, ...]:
    """Parse manifest records without changing their durable source metadata."""
    if manifest.get("schema_version") != "evidence-manifest.v1":
        raise ValueError("expected evidence-manifest.v1")
    records: list[Evidence] = []
    for raw in manifest.get("evidence", []):
        if not isinstance(raw, Mapping):
            raise ValueError("manifest evidence records must be objects")
        text = str(raw.get("text", ""))
        source = raw.get("source", {})
        if not isinstance(source, Mapping):
            raise ValueError("evidence source must be an object")
        records.append(
            Evidence(
                evidence_id=str(raw["evidence_id"]),
                document_name=str(raw["document_name"]),
                document_sha256=str(raw["document_sha256"]),
                page=int(raw["page"]),
                text=text,
                source=dict(source),
                text_sha256=str(raw.get("text_sha256", _sha256_text(text))),
                render_sha256=str(raw.get("render_sha256", "")),
                visual_description=str(raw.get("visual_description", "")),
                page_title=str(raw.get("page_title", "")),
                adjacent_metadata=str(raw.get("adjacent_metadata", "")),
                image_width=int(raw.get("image_width", 0) or 0),
                image_height=int(raw.get("image_height", 0) or 0),
            )
        )
    return tuple(sorted(records, key=_stable_key))


def _coerce_evidence(raw: Evidence | Mapping[str, Any]) -> Evidence:
    if isinstance(raw, Evidence):
        return raw
    metadata = raw.get("metadata", {})
    metadata = metadata if isinstance(metadata, Mapping) else {}
    image = raw.get("image", {})
    image = image if isinstance(image, Mapping) else {}
    text = str(raw.get("text", ""))
    return Evidence(
        evidence_id=str(raw["evidence_id"]),
        document_name=str(raw.get("document_name", raw.get("source", {}).get("path", ""))),
        document_sha256=str(raw.get("document_sha256", "")),
        page=int(raw.get("page", 0)),
        text=text,
        source=dict(raw.get("source", {"path": raw.get("document_name", ""), "page": raw.get("page", 0)})),
        text_sha256=str(raw.get("text_sha256", _sha256_text(text))),
        render_sha256=str(raw.get("render_sha256", "")),
        visual_description=str(raw.get("visual_description", "")),
        page_title=str(raw.get("page_title", metadata.get("title", ""))),
        adjacent_metadata=" ".join(str(v) for v in metadata.get("adjacent", [])),
        image_width=int(raw.get("image_width", image.get("width", 0)) or 0),
        image_height=int(raw.get("image_height", image.get("height", 0)) or 0),
    )


def _deduplicate(items: Iterable[RetrievedEvidence]) -> list[RetrievedEvidence]:
    """Deduplicate equivalent text/renders, keeping the best stable candidate."""
    seen: set[str] = set()
    result: list[RetrievedEvidence] = []
    for item in sorted(items, key=lambda x: (-x.score, _stable_key(x.evidence))):
        evidence = item.evidence
        text_key = evidence.text_sha256 or _sha256_text(evidence.text)
        render_key = evidence.render_sha256
        keys = [f"text:{text_key}"] if text_key else []
        if render_key:
            keys.append(f"render:{render_key}")
        if any(key in seen for key in keys):
            continue
        seen.update(keys)
        result.append(item)
    return result


class BM25:
    """Small, dependency-free BM25 index with deterministic tie-breaking."""

    def __init__(self, evidence: Sequence[Evidence], *, k1: float = 1.2, b: float = 0.75) -> None:
        if k1 < 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 >= 0 and 0 <= b <= 1")
        self.evidence = tuple(sorted(evidence, key=_stable_key))
        self.k1, self.b = k1, b
        self._doc_tokens = tuple(_tokens(item.index_text) for item in self.evidence)
        self._lengths = tuple(len(tokens) for tokens in self._doc_tokens)
        self._average_length = sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        frequencies: Counter[str] = Counter()
        for tokens in self._doc_tokens:
            frequencies.update(set(tokens))
        self._idf = {
            term: math.log(1 + (len(self.evidence) - count + 0.5) / (count + 0.5))
            for term, count in frequencies.items()
        }

    def search(self, query: str, *, retrieve_k: int = 50) -> tuple[RetrievedEvidence, ...]:
        if retrieve_k < 0:
            raise ValueError("retrieve_k must be non-negative")
        query_terms = Counter(_tokens(query))
        scored: list[RetrievedEvidence] = []
        for index, (item, terms) in enumerate(zip(self.evidence, self._doc_tokens)):
            counts = Counter(terms)
            score = 0.0
            for term, query_frequency in query_terms.items():
                if term not in counts:
                    continue
                denominator = counts[term] + self.k1 * (
                    1 - self.b + self.b * len(terms) / self._average_length
                ) if self._average_length else 1.0
                score += self._idf.get(term, 0.0) * (
                    counts[term] * (self.k1 + 1) / denominator
                ) * min(query_frequency, 1)
            if score > 0:
                scored.append(RetrievedEvidence(item, score, index + 1))
        scored.sort(key=lambda x: (-x.score, _stable_key(x.evidence)))
        return tuple(replace(item, rank=rank) for rank, item in enumerate(scored[:retrieve_k], 1))


def _lexical_similarity(left: Sequence[str], right: Sequence[str]) -> float:
    a, b = set(left), set(right)
    return len(a & b) / len(a | b) if a | b else 0.0


def _mmr(
    items: Sequence[RetrievedEvidence],
    *,
    limit: int,
    per_document_cap: int,
    mmr_lambda: float = 0.85,
) -> list[RetrievedEvidence]:
    candidates = list(items)
    selected: list[RetrievedEvidence] = []
    document_counts: defaultdict[str, int] = defaultdict(int)
    while candidates and len(selected) < limit:
        eligible = [item for item in candidates if document_counts[item.evidence.document_sha256] < per_document_cap]
        if not eligible:
            break
        def choice_key(item: RetrievedEvidence) -> tuple[float, float, tuple[str, int, str]]:
            redundancy = max((_lexical_similarity(_tokens(item.evidence.index_text), _tokens(other.evidence.index_text)) for other in selected), default=0.0)
            value = mmr_lambda * item.score - (1 - mmr_lambda) * redundancy
            return (value, item.score, _stable_key(item.evidence))
        chosen = min(eligible, key=lambda item: (-choice_key(item)[0], -choice_key(item)[1], choice_key(item)[2]))
        selected.append(chosen)
        document_counts[chosen.evidence.document_sha256] += 1
        candidates.remove(chosen)
    return selected


def retrieve(
    query: str,
    evidence: Sequence[Evidence | Mapping[str, Any]],
    *,
    retrieve_k: int = 50,
    k1: float = 1.2,
    b: float = 0.75,
    reranker: Reranker | None = None,
    diversify_k: int = 8,
    per_document_cap: int = 2,
    mmr_lambda: float = 0.85,
) -> tuple[RetrievedEvidence, ...]:
    """Retrieve, optionally rerank, deduplicate, and lexically diversify pages."""
    typed_evidence = tuple(_coerce_evidence(item) for item in evidence)
    candidates = BM25(typed_evidence, k1=k1, b=b).search(query, retrieve_k=retrieve_k)
    if reranker is not None:
        rerank = reranker.rerank if hasattr(reranker, "rerank") else reranker
        candidates = tuple(rerank(query, candidates))
    return tuple(
        _mmr(
            _deduplicate(candidates),
            limit=diversify_k,
            per_document_cap=per_document_cap,
            mmr_lambda=mmr_lambda,
        )
    )


def _expand(item: Evidence, lookup: Mapping[str, Evidence]) -> Evidence:
    """Add only title/adjacent metadata already present in the manifest."""
    parts = [item.page_title, item.adjacent_metadata]
    if not any(parts):
        previous = lookup.get(f"{item.document_sha256}:p{item.page - 1}")
        following = lookup.get(f"{item.document_sha256}:p{item.page + 1}")
        adjacent = [p.text.splitlines()[0].strip() for p in (previous, following) if p and p.text.strip()]
        parts = [part for part in adjacent if part]
    metadata = " ".join(dict.fromkeys(part for part in parts if part))
    return replace(item, adjacent_metadata=metadata, expanded_metadata={"title": item.page_title, "adjacent": metadata.split() if metadata else []})


def bind_citations(evidence: Sequence[Evidence]) -> tuple[CitationBinding, ...]:
    return tuple(
        CitationBinding(
            f"SOURCE_{number}",
            item.evidence_id,
            {
                **dict(item.source),
                "document_name": item.document_name,
                "document_sha256": item.document_sha256,
                "page": item.page,
            },
        )
        for number, item in enumerate(evidence, 1)
    )


def resolve_citations(
    citations: Iterable[str], bindings: Sequence[CitationBinding]
) -> tuple[CitationBinding, ...]:
    """Resolve model citation labels only against the admitted context."""
    by_label = {binding.citation: binding for binding in bindings}
    resolved: list[CitationBinding] = []
    for citation in citations:
        try:
            resolved.append(by_label[citation])
        except KeyError as exc:
            raise ValueError(f"citation is outside admitted context: {citation}") from exc
    return tuple(resolved)


def pack_evidence(
    items: Sequence[RetrievedEvidence | Evidence],
    *,
    token_budget: int = 4096,
    image_budget: int = 2,
    pixel_budget: int = 1280 * 1280 * 2,
    page_budget: int = 2,
) -> tuple[Evidence, ...]:
    """Pack whole pages under hard text-token, image-count, and pixel bounds."""
    if min(token_budget, image_budget, pixel_budget, page_budget) < 0:
        raise ValueError("packing budgets must be non-negative")
    packed: list[Evidence] = []
    tokens = images = pixels = 0
    for candidate in items:
        item = candidate.evidence if isinstance(candidate, RetrievedEvidence) else candidate
        item_tokens = len(_tokens(item.text)) + len(_tokens(item.visual_description))
        item_images = 1 if item.pixels else 0
        item_pixels = item.pixels
        if len(packed) >= page_budget:
            break
        if tokens + item_tokens > token_budget or images + item_images > image_budget or pixels + item_pixels > pixel_budget:
            continue
        packed.append(item)
        tokens += item_tokens
        images += item_images
        pixels += item_pixels
    return tuple(packed)


class BM25Retriever:
    """Mapping-compatible adapter around the typed BM25 implementation."""

    def __init__(self, records: Sequence[Mapping[str, Any]], *, k1: float = 1.2, b: float = 0.75) -> None:
        self._records = tuple(_coerce_evidence(record) for record in records)
        self._index = BM25(self._records, k1=k1, b=b)

    def search(self, query: str, *, limit: int = 50) -> list[Evidence]:
        return [item.evidence for item in self._index.search(query, retrieve_k=limit)]


class NoOpReranker:
    def rerank(self, _query: str, candidates: Sequence[Any]) -> list[Any]:
        return list(candidates)


def bind_source_citations(evidence: Sequence[Evidence | Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    typed = [_coerce_evidence(item) for item in evidence]
    return {
        binding.citation: {"evidence_id": binding.evidence_id, **dict(binding.source)}
        for binding in bind_citations(typed)
    }


def assemble_context(
    query: str,
    evidence: Sequence[Evidence | Mapping[str, Any]],
    *,
    retrieve_k: int = 50,
    diversify_k: int = 8,
    per_document_cap: int = 2,
    token_budget: int = 4096,
    image_budget: int = 2,
    pixel_budget: int = 1280 * 1280 * 2,
    page_budget: int = 2,
    reranker: Reranker | None = None,
    mmr_lambda: float = 0.85,
) -> Context:
    """Build ordered, cited context or fail fast with an abstention result."""
    if not 0 <= mmr_lambda <= 1:
        raise ValueError("mmr_lambda must be between 0 and 1")
    typed_evidence = tuple(_coerce_evidence(item) for item in evidence)
    ranked = retrieve(
        query,
        typed_evidence,
        retrieve_k=retrieve_k,
        diversify_k=diversify_k,
        per_document_cap=per_document_cap,
        reranker=reranker,
        mmr_lambda=mmr_lambda,
    )
    lookup = {item.evidence_id: item for item in typed_evidence}
    expanded = [replace(item, evidence=_expand(item.evidence, lookup)) for item in ranked]
    packed = pack_evidence(
        expanded,
        token_budget=token_budget,
        image_budget=image_budget,
        pixel_budget=pixel_budget,
        page_budget=page_budget,
    )
    if not packed:
        return Context((), (), "", True, "zero_admissible_evidence")
    citations = bind_citations(packed)
    sections = [f"{binding.citation} [{item.document_name} p.{item.page}]\n{item.text}" for binding, item in zip(citations, packed)]
    return Context(packed, citations, "\n\n".join(sections), False)


def retrieve_context(
    manifest: Mapping[str, Any],
    query: str,
    *,
    model_dispatch: Callable[[Context], Any] | None = None,
    **kwargs: Any,
) -> Context:
    """Assemble context and invoke a model only when evidence is admissible."""
    context = assemble_context(query, evidence_from_manifest(manifest), **kwargs)
    if not context.abstained and model_dispatch is not None:
        model_dispatch(context)
    return context
