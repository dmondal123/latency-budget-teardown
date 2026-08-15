# Chunking and Embedding — Detail Reference

Covers stages 3-5 from the building-rag-pipelines skill.

## Stage 3 — Chunking

Chunk at semantic boundaries, never fixed bytes. Keep a rule and its qualifying exception in the same retrievable unit.

Suggested defaults:

- `chunk_size = 1024`
- `chunk_overlap = 200`

Always check the embedding model's maximum input length before setting chunk size. Overlap protects boundary facts, but it also creates near-duplicates, so dedupe after chunking.

## Stage 4 — Chunk labeling

Every chunk must carry:

- `chunk_id`
- `parent_id`
- `source_span`
- `source_version`
- `acl`

Store the chunk metadata in a durable, queryable store. If the span or version was not stored at index time, it cannot be reconstructed later.

## Stage 5 — Embedding

Use an asymmetric bi-encoder with separate paths for queries and documents. Do not use the default symmetric `encode()` unless the model is designed for it.

Metric and normalization are one contract. If the index was built with normalized vectors and cosine similarity, query-time retrieval must use the same geometry.

Any change to model, version, or normalization invalidates the entire vector index. Regenerate all vectors before accepting query traffic.
