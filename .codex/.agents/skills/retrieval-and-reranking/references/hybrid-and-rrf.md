# Hybrid Retrieval and Reranker Configuration

## Reranker model

Use a cross-encoder reranker. It concatenates query and passage into one sequence and emits a single relevance score. If you need a 0-1 score, apply sigmoid to the raw logits.

## Shortlist and context budget

- Retrieve roughly 50-200 candidates.
- Rerank them all.
- Treat fewer than about 25 reranked candidates as a recall problem.
- Keep `top_context` configurable and tied to the context budget.

## Worked example

The reranker should raise the actual answer passages and demote obsolete or off-topic passages. Log first-stage rank versus reranked rank for key passages in eval sets.

## Hybrid retrieval

BM25 retrieves lexical matches, dense KNN retrieves semantic matches, and Reciprocal Rank Fusion merges the ranked lists into a single shortlist.

Use the normal BM25 defaults (`k1=1.2`, `b=0.75`) and RRF default `rank_constant=60` unless a labelled eval set says otherwise.

## Retrieve-rerank-pack flow

1. Retriever returns 50-200 candidates.
2. Reranker scores the shortlist.
3. Select top_context by rerank score.
4. Pass the selected set into context assembly layers 2-7.

Critical rule: `top_context` is a ceiling on what enters layer 2, not a promise about what reaches the prompt.
