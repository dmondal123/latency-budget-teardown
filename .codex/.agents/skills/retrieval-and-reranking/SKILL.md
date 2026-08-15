---
name: retrieval-and-reranking

description: Use when improving retrieval quality or assembling context for a RAG prompt. Covers hybrid retrieval (BM25 + dense + RRF), cross-encoder vs bi-encoder reranking, and the 8-layer context-assembly pipeline with hard ordering constraints. Rigid ordering.
---

# Retrieval and Reranking

## Purpose

Turn a first-stage shortlist into a high-precision, well-ordered, cited context block. Reranking is often the single largest quality gain per hour of engineering.

## When to use

When retrieval rank is being used as a proxy for context quality, or when building the retrieve-rerank-pack path. Part of the pipeline in [[building-rag-pipelines]].

## Bi-encoder vs cross-encoder

- Bi-encoder (retriever): encodes query and passage separately; scores the corpus; optimizes recall.
- Cross-encoder (reranker): concatenates query and passage, uses full cross-attention, is expensive, and should see only the shortlist; optimizes precision.

Retrieve 50-200 candidates, rerank all of them, and treat reranking fewer than about 25 candidates as a recall problem, not a precision problem. A reranker cannot rescue a passage that was never retrieved.

## The 8-layer context assembly

0. Top-k baseline
1. Rerank
2. Dedupe
3. Diversify
4. Expand
5. Pack
6. Order
7. Cite

Hard constraints: rerank before dedupe and diversify; dedupe before diversify; diversify before expand; expand before pack; pack before order; assign evidence IDs at or before dedupe.

## References

`references/context-assembly-layers.md` — each layer's mechanism, anti-patterns, and metrics

`references/hybrid-and-rrf.md` — BM25 + dense + RRF parameters

## Related skills

[[building-rag-pipelines]] [[evaluating-llm-systems]] [[reducing-llm-latency]]
