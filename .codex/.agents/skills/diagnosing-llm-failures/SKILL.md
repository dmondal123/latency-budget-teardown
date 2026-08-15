---
name: diagnosing-llm-failures

description: Use when an LLM/RAG system produces a wrong output, regression, or incident. Covers the 6 failure classes, the truth/evidence matrix, and the 8-step triage loop that finds the earliest broken invariant, not the last symptom. Rigid.
---

# Diagnosing LLM Failures

## Purpose

Classify and root-cause failures by the earliest broken pipeline invariant. Everything after the first divergence is a symptom.

## When to use

Any bug, regression, or wrong or unsupported output. Pairs with the regression step of [[evaluating-llm-systems]] and the stages of [[building-rag-pipelines]].

## Six failure classes

Walk in order and stop at the first "no".

1. Hallucination — stage 4, atomic claim false? model/eval
2. Instruction failure — stage 2, obeyed every surviving constraint? prompt/policy
3. Grounding failure — stages 3-4, cited evidence supports this claim/entity/version? retrieval/RAG
4. Formatting failure — stage 5, can the consumer parse and validate the payload? API contract
5. Tool failure — stage 6, right tool, called correctly, result handled? orchestration
6. Integration failure — stages 7-8, state exists once and is visible to the right user? platform

## Truth × evidence matrix

True + supported: no failure.

True + unsupported: grounding failure.

False + supported: hallucination primary, corpus secondary.

False + unsupported: both; the earlier label owns the fix.

One incident gets one primary root plus unlimited secondary labels. Severity comes from consequence, not class.

## 8-step triage loop

1. Contain
2. Reproduce
3. Specify
4. Replay
5. Localise
6. Label
7. Repair
8. Regress

## References

`references/failure-taxonomy.md` — class table, matrix, and severity

`references/triage-loop.md` — each step's actions and reproduce bundle contents

## Related skills

[[evaluating-llm-systems]] [[building-rag-pipelines]] [[retrieval-and-reranking]]
