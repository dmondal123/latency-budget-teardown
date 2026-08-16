"""Text-corpus ingestion package."""

from .corpus import ingest_from_materialization, load_cached_passages
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
    "ingest_from_materialization",
    "load_cached_passages",
    "load_huggingface",
    "materialize",
    "normalize_text",
    "normalized_corpus_hash",
]
