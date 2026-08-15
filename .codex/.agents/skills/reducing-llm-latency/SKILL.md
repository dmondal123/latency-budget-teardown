---
name: reducing-llm-latency

description: Use when reducing latency, perceived latency, or token cost in an LLM/RAG system. Covers optimization order, the four clocks, token-cost denominators, streaming, and failure-mode signatures.
---

# Reducing LLM Latency

## Purpose

Cut latency and cost without weakening the evidence or validation contract. Measure before optimizing; optimize in a strict order.

## When to use

Any latency, performance, or cost work. Latency and cost also gate promotion in [[evaluating-llm-systems]]; a smaller working set improves both retrieval and generation from [[building-rag-pipelines]].

## Optimization order

1. Delete unnecessary work.
2. Parallelize independent work off the critical path, or prewarm.
3. Fail fast, then deepen.
4. Bound every loop.
5. Cache stable prefixes and prewarm environments.
6. Protect the evidence; shorten narration first, never weaken required validation.
7. Choose a faster model only after 1-6 are exhausted.

## The four clocks

Emit and record all four separately:

- TTFE — time to first event
- TTFT — time to first token
- TTA — time to first action
- TTC — time to validated completion

Parallel branches compose as max(A, B), not A + B. Do not sum p95s.

## Cost

Report cost per completed task, not per call. Log input and output tokens separately. Failed attempts bill in full.

## References

`references/optimization-order.md` — each law's techniques, streaming, and retry classification

`references/four-clocks-and-cost.md` — clocks, instrumentation, cost denominators, failure signatures

## Related skills

[[evaluating-llm-systems]] [[selecting-models]] [[building-rag-pipelines]] [[retrieval-and-reranking]]
