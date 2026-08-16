"""Text-corpus ingestion package."""

from .corpus import TextRagError, ingest_from_materialization, ingest_passages, load_cached_passages, normalize_text
from .materialize import (
    CONFIGURATIONS,
    DATASET_REPOSITORY,
    DATASET_REVISION,
    LoadedRows,
    MaterializationError,
    load_huggingface,
    materialize,
    normalize_text,
    normalized_corpus_hash,
)

__all__ = [
    "CONFIGURATIONS",
    "DATASET_REPOSITORY",
    "DATASET_REVISION",
    "LoadedRows",
    "MaterializationError",
    "TextRagError",
    "ingest_from_materialization",
    "ingest_passages",
    "load_cached_passages",
    "load_huggingface",
    "materialize",
    "normalize_text",
    "normalized_corpus_hash",
]
