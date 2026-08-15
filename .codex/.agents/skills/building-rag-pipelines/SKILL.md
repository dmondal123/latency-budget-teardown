---
name: building-rag-pipelines

description: Use when building, scaffolding, or reviewing a RAG system end to end. Covers the full 17-stage anatomy from evidence routing through ingestion, chunking, embedding, indexing, retrieval, generation, and citation. Flexible design skill.
---

# Building RAG Pipelines

## Purpose

Guide the design of a production RAG pipeline as 17 explicit stages, each with a clear responsibility and the key decisions and heuristics for it. Adapt the choices to corpus and constraints.

## When to use

Scaffolding a new RAG system, adding a stage, or reviewing whether a pipeline has the right seams. For retrieval-quality depth see [[retrieval-and-reranking]]; for very large corpora see [[rlm-based-rag]]; always pair with [[evaluating-llm-systems]].

## The 17 stages

0. Evidence routing
1. Ingestion
2. Parsing
3. Chunking
4. Chunk labeling
5. Embedding
6. Indexing / ANN
7. Hybrid retrieval
8. Security trimming
9. Query planning
10. Reranking
11. Entity resolution
12. Context packing
13. Generation
14. Citation binding
15. Evaluation
16. Governed actions

## Cross-cutting rules

- A retrieval miss is invisible downstream; `RETRIEVED PASSAGES: 0` must suppress or flag the response.
- Vectors are an ephemeral cache; chunk metadata is the durable evidence contract.
- Provenance and citation correctness are separate checks.

## References

- `references/pipeline-stages.md` — stages 0-2, 6-7, 9, 11, and 16
- `references/chunking-and-embedding.md` — stages 3-5
- `references/security-and-generation.md` — stages 8, 13-15

## Related skills

[[retrieval-and-reranking]] [[rlm-based-rag]] [[evaluating-llm-systems]] [[diagnosing-llm-failures]]
