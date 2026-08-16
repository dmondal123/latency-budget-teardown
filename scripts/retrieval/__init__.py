"""Text-only retrieval package for deterministic BM25 evidence selection."""

from .bm25 import BM25Index, Passage, RetrievedPassage, RetrievalError, build_index, retrieve
from .context import AssembledContext, assemble_context

__all__ = [
    "AssembledContext",
    "BM25Index",
    "Passage",
    "RetrievedPassage",
    "RetrievalError",
    "assemble_context",
    "build_index",
    "retrieve",
]
