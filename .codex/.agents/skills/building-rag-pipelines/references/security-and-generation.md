# Security and Generation — Detail Reference

Covers stages 8, 13-15 from the building-rag-pipelines skill.

## Stage 8 — Security trimming

Apply ACL filters inside the KNN or ANN query, never as a post-filter. For hybrid retrieval, verify the ACL filter on every branch independently.

Mirrored ACL indexes always have revocation latency. Define and document a revocation latency SLA, and build a reconciliation audit that can answer what the state of an item was in the index at time T.

Never rely on UI citation hiding as a security control.

## Stage 13 — Generation

Write the evidence contract as a system-prompt section that is always present and never overrideable by retrieved content.

The contract should specify:

1. Which sources count as evidence
2. How to mark citations
3. When to qualify uncertainty
4. Abstention triggers for missing evidence

Use `SOURCE_1` through `SOURCE_N` instead of filenames. Add a data-boundary instruction that treats retrieved text as untrusted input.

## Stage 14 — Citation binding

Citation begins at ingestion. Parent IDs, page or row spans, versions, and URLs must be on the chunk at index time.

Displaying a citation link proves provenance, not entailment. Add a post-generation citation checker that verifies the cited span actually supports the claim.

Track `citation_precision` in the eval pipeline.

## Stage 15 — Evaluation

Never rely on a single answer-quality aggregate. Evaluate each seam independently, include ACL and freshness checks, and keep the golden set versioned.
