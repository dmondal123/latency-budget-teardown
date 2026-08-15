# RLM Architecture, Parameters, and Load-Bearing Implementation Details

Derived from the RLM paper and repository commit `cafebff`.

## What RLM is

RLM stands for Recursive Language Model.

## Classic RAG vs RLM

Classic RAG decides what is read before the model sees the corpus. RLM gives the root model only the query, stores the corpus in a REPL variable, and lets the model write code to probe and dispatch sub-queries adaptively.

## Core problem: context rot

Context rot is accuracy falling as prompt length grows, even when nothing is truncated.

## Why classic alternatives fail

- BM25 retrieve-then-read can rank the relevant document far down the list because of vocabulary mismatch.
- Compaction or summarization fails on relational questions because it discards cross-references.

## 7-step architecture

0. Baseline model(question + corpus)
1. Corpus as REPL variable; root prompt is question only
2. Model writes probes in `repl` blocks; REPL executes
3. `llm_query` / `llm_query_batched` injected as semantic matchers
4. `rlm_query` / `rlm_query_batched` recursive child RLM
5. Findings stored in REPL variables; coverage via set arithmetic
6. `answer["ready"] = True` termination sentinel

## Key parameters and defaults

Document the maximum iterations, maximum depth, maximum concurrent subcalls, budget, timeout, token cap, error cap, and stdout cap. Do not raise the stdout cap; it prevents re-importing corpus through print.

## Depth heuristic

Depth is not a quality dial. Treat max_depth as a per-model, per-task hyperparameter and evaluate accuracy and cost.

Some models and tasks improve with depth; others collapse. Cost can also rise sharply as depth increases, so per-task breakdowns are required.
