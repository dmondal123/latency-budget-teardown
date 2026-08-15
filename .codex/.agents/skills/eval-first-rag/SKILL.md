---
name: eval-first-rag

description: Use when building and shipping a RAG system end to end and you want to reduce latency without regressing quality. This orchestrating workflow runs eval-first, builds the pipeline, instruments the four clocks, optimizes latency in strict order, and gates promotion on quality and latency/cost. Delegates into the focused RAG skills.
---

# Eval-First RAG (Orchestrator)

## Purpose

Sequence the whole build-evaluate-optimize loop so latency is reduced against a frozen quality bar, never at its expense. This skill delegates; depth lives in the focused skills.

## When to use

"Make a RAG pipeline and evaluate it to reduce latency," or any end-to-end RAG build.

## Workflow

1. Define the behavioral contract and eval suite first: [[evaluating-llm-systems]].
2. Choose the approach: classic pipeline [[building-rag-pipelines]] and, if context rot dominates a large corpus, [[rlm-based-rag]]. Pick models via [[selecting-models]].
3. Build the pipeline stages; assemble context via [[retrieval-and-reranking]].
4. Instrument the four clocks and the quality vector on every eval row: [[reducing-llm-latency]].
5. Run the frozen suite; if a failure appears, root-cause via [[diagnosing-llm-failures]].
6. Reduce latency in strict order, rerunning the suite after each change: [[reducing-llm-latency]].
7. Gate promotion on fatal count, quality thresholds, p95 latency, cost, and slice regressions. Only then ship.
8. Feed incidents back into the suite.

## Guardrail

Never weaken required validation to hit a latency target. Latency wins come from deleting work and caching, not from lowering the bar.

## Related skills

[[evaluating-llm-systems]] [[building-rag-pipelines]] [[retrieval-and-reranking]] [[rlm-based-rag]] [[reducing-llm-latency]] [[selecting-models]] [[diagnosing-llm-failures]]
