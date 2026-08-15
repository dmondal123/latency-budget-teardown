# Optimization Order — Techniques, Streaming, and Retry Classification

All figures are illustrative design allocations from the source material.

## The seven laws

Apply strictly in sequence:

1. Delete unnecessary work.
2. Parallelize independent work and prewarm.
3. Fail fast, then deepen.
4. Bound every loop.
5. Cache stable prefixes and environments.
6. Protect the evidence.
7. Choose a faster model only after 1-6 are exhausted.

## Law 1 — delete unnecessary work

Do not retrieve files nobody reads, narrate obvious steps, rerun checks on unchanged inputs, or serialize tool output the model will never look at.

## Law 2 — parallelize independent work, or prewarm

Parallel branches compose as max(A, B), not A + B. Only overlap work with disjoint read and write sets. Prewarming sandboxes and interpreters is usually the cheapest latency win.

## Law 3 — fail fast, then deepen

Order validation gates by information per second.

## Law 4 — bound every loop

Cap turns, output tokens per turn role, retries, tool wall time, and validation scope. Define what happens at each cap.

## Law 5 — cache stable prefixes and environments

Cache repo rules, skill metadata, skill headers, and system instructions. Cache savings are real but shrink as dynamic context dominates.

## Law 6 — protect the evidence

When the deadline gets tight, shorten narration and optional checks first. Weakening required validation is not latency optimization; it is a product change.

## Law 7 — faster model

Do not reach for a faster model until the structural fixes are exhausted.

## Streaming

Streaming reduces perceived wait time and enables steering, but it does not speed up validation work. Emit events only on real state transitions.

## Retry classification

One layer owns retries. Inner layers return typed failure plus idempotency key and must not retry independently.

Classify before retrying:

- transient provider or network failure: repeat unchanged, with backoff
- failed test: new hypothesis required
- invalid patch or schema: repair the artifact, same hypothesis
- permission denied: stop and escalate to a human
- deadline exceeded: stop and return partial evidence

## Context and prompt size

Treat token budget as a hard cap. Reduce retrieved tokens first; reserve output tokens first; never let the budget become an emergent property of concatenation.
