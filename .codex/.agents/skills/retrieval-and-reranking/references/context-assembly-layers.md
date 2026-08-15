# Context Assembly Layers — Mechanism and Detail

## Overview

The eight layers sit between raw retrieval results and the final prompt. They decide what is relevant, distinct, well-ordered, and attributable.

- Layers 0-1 decide what is relevant.
- Layers 2-3 decide what is distinct.
- Layers 4-7 decide what the prompt looks like.

## Layer 0 — top-k

Sort by retriever similarity, cut at k, and concatenate raw chunks in retrieval order.

What it adds: lexical or embedding similarity.

Why it fails: similarity to the query string does not guarantee coverage of all clauses.

## Layer 1 — rerank

A cross-encoder reads the query and passage jointly and emits a relevance score.

What it adds: direct query-passage relevance.

Hard floor: reranking cannot recover passages that were never retrieved.

## Layer 2 — dedupe

Cluster near-identical passages using normalized text first, then embedding similarity. Elect the most complete, most recently versioned copy as canonical.

What it adds: identity signal.

Ordering constraint: dedupe before diversify.

## Layer 3 — diversify

Use greedy MMR selection.

What it adds: marginal novelty relative to the selected set.

Anti-pattern: do not diversify before establishing relevance.

## Layer 4 — expand

Walk up the document structure from the hit and attach the section heading and neighboring sentences up to the section boundary.

What it adds: structural context.

Anti-pattern: do not expand every candidate.

## Layer 5 — pack

Count rendered tokens per unit, including the citation header, and admit whole units while they fit.

What it adds: explicit token budgeting.

Hard rule: never partially admit a unit.

## Layer 6 — order

Classify admitted units by argument role, then emit them in reasoning order: direct rule, applicability, limiting condition.

What it adds: argument role, not relevance rank.

Anti-pattern: emitting in score order.

## Layer 7 — cite

Assign stable evidence IDs at admission time, render the IDs in the block header, include source metadata, and resolve IDs back to document metadata at display time.

What it adds: provenance.

Anti-pattern: cite chunk indices.

## Hard ordering constraints

1. Rerank before dedupe and diversify.
2. Dedupe before diversify.
3. Diversify before expand.
4. Expand before pack.
5. Pack before order.
6. Assign evidence IDs before or at dedupe.

## Anti-patterns

Do not treat retrieval score as context quality, deduplicate by exact hash only, diversify before relevance, expand every candidate, truncate a unit to fit, emit in score order, or cite chunk IDs.
