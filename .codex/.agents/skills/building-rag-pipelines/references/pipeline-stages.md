# Pipeline Stages — Detail Reference

Covers stages 0-2, 6-7, 9, 11, and 16 from the building-rag-pipelines skill.

## Stage 0 — Evidence routing

Decompose by authority, freshness, scale, and structure. Route each sub-question to the narrowest mechanism that can answer it: deterministic search, long context, RAG, tool call, or fine-tuning after evals.

Rules:

- Never force a single default mechanism.
- Carry evidence as distinct typed items with provenance.
- Evaluate each leg separately: exact record correctness, tool freshness, retrieval recall, answer grounding, latency, cost, and contract conformance.
- Fine-tuning is not a fifth runtime evidence source.

## Stage 1 — Ingestion

Each connector must understand the source object model, not just the text body.

Pull content, identity, structure, and permissions. Ingest ACLs atomically with content.

The three sync pipelines are:

1. Incremental upsert
2. Tombstone/delete propagation
3. Full reconciliation

Log source-change lag and verify that each source is addressable before query traffic is allowed.

## Stage 2 — Parsing

Build a registry keyed by MIME type or source system. Use layout-aware extraction for PDFs, slides, spreadsheets, and scans. Preserve page and position metadata.

Never use plain `pdftotext` when layout matters. After parsing, validate structural integrity and reject documents that lack page or position metadata.

## Stage 6 — Indexing / ANN

Use HNSW or IVF with the right knobs for your corpus. Treat `top_k` as a recall ceiling: if the decisive passage is absent from top-k, reranking cannot promote it later.

## Stage 7 — Hybrid retrieval

Run BM25 and dense KNN in parallel, then merge with RRF. Validate both branches independently before trusting the fused list.

## Stage 8 — Security trimming

Apply ACL filters inside retrieval, never as a post-filter. A filter on only one branch leaves the other branch unsecured.

## Stage 9 — Query planning

Decompose compound questions into typed sub-queries by evidence type: rationale, rule, event, role. Define an explicit stop condition before deploying agentic retrieval.

## Stage 11 — Entity resolution

Resolve multi-system aliases to canonical IDs before or after retrieval, but not inside generation. Use role-at-event-time, not current role.

## Stage 16 — Governed actions

For enterprise actions, use typed actions, human-in-the-loop approval, and audit records.
