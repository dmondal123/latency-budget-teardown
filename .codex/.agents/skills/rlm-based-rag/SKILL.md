---
name: rlm-based-rag

description: Use when a corpus is large enough that classic top-k RAG suffers context rot, or when retrieval strategy should be chosen adaptively after probing the data. Covers Recursive Language Model (RLM) RAG, its 7-step architecture, and the depth-as-hyperparameter heuristic. Advanced/optional.
---

# RLM-Based RAG

## Purpose

An alternative to classic retrieve-then-read: give the root model only the query, store the corpus in a REPL variable, and let the model write code to probe, partition, and dispatch sub-queries adaptively. Solves context rot, where accuracy degrades as prompt length grows even without truncation.

## When to use

Large or mutable corpora, relational or cross-document questions, or when a fixed retrieval strategy is the bottleneck. Prefer it over classic RAG when context rot dominates. Do not use a compaction or summarization strategy when the task needs cross-document references.

## 7-step architecture

0. Baseline model(question + corpus) — establishes the floor.
1. Corpus as REPL variable `context`; root prompt = question only.
2. Model writes probes in `repl` blocks; REPL executes.
3. `llm_query` / `llm_query_batched` injected for semantic matching.
4. `rlm_query` / `rlm_query_batched` recursive child RLM.
5. Findings in REPL vars; coverage via set arithmetic.
6. `answer["ready"] = True` termination sentinel.

## Critical heuristic

Depth is not always better. Treat max_depth as a per-model, per-task hyperparameter; evaluate accuracy and cost, never aggregate averages.

## References

`references/architecture-and-params.md` — defaults and load-bearing implementation details

## Related skills

[[building-rag-pipelines]] [[evaluating-llm-systems]] [[selecting-models]]
