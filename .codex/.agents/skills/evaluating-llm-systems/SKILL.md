---
name: evaluating-llm-systems

description: Use when evaluating, gating, or shipping any LLM/RAG change. Covers eval-first engineering, the 9-mechanism ladder, dataset slicing, the quality vector, LLM-as-judge calibration, fatal gates, harness persistence, and the promotion predicate that includes latency and cost. Rigid.
---

# Evaluating LLM Systems

## Purpose

Replace vibes-driven iteration with a frozen, rerunnable, versioned eval that decides promotion. An eval is a behavioral contract, a named input distribution, an oracle per criterion, and a rerunnable record.

## When to use

Before shipping any prompt, model, retrieval, or tool change. This is the first step of [[eval-first-rag]] and the gate for [[building-rag-pipelines]] and [[reducing-llm-latency]].

## The 9-mechanism ladder

Build in order; diagnose backward.

1. Draw the behavioral boundary: a versioned may/must_not contract.
2. Split "good" into named dimensions: a quality vector, never blended.
3. Turn harms into vetoes: boolean fatal gates.
4. Freeze thresholds before seeing candidates: dated file plus owner.
5. Recreate traffic: slices for typical, edge, adversarial, and ambiguous cases, plus a sealed holdout.
6. Give every criterion an oracle: code, model, or human; use the cheapest one that can decide.
7. Make the contract executable: harness stores raw output, scores, and stamps.
8. Make every change earn promotion: CI gate.
9. Feed reality back: minimize incidents, add cases, rerun the full suite.

## Key rules

Latency and cost are eval dimensions. Put latency_p50_ms, latency_p95_ms, and cost_per_request in the same row as quality scores. See [[reducing-llm-latency]].

Never use a blended score. Ban the word "accuracy"; require a dimension name.

Harms cannot be averaged. Fatal gates hard-block the run.

Calibrate any LLM judge against human labels before it gates anything.

## Promotion predicate

Example:

fatal_count=0 AND groundedness>=0.95 AND resolution>=0.85 AND p95_latency_ms=1800 AND cost_per_reply<=0.02 AND no_slice_regresses (tol=0.02)

## References

`references/ladder-and-datasets.md` — the 9 rungs, slice families, and quality vector table

`references/judges-gate-harness.md` — judge calibration, fatal gates, harness persistence, reliability layers

## Related skills

[[building-rag-pipelines]] [[reducing-llm-latency]] [[diagnosing-llm-failures]] [[selecting-models]]
