# Failure Taxonomy

## Core model: eight pipeline stages, eight invariants

Every agent request passes through eight stages. The root cause is the earliest stage whose invariant broke.

| Group | Stage # | Stage name | Invariant |
| --- | --- | --- | --- |
| Intent | 1 | Goal | Constraints captured |
| Intent | 2 | Plan | Instructions still apply |
| Knowledge | 3 | Evidence | Support retrieved |
| Knowledge | 4 | Answer | Claims true and entailed |
| Contract and action | 5 | Schema | Contract satisfied |
| Contract and action | 6 | Tool | Action really executed |
| Business state | 7 | App state | State persisted once |
| Business state | 8 | Outcome | User sees the truth |

## Six failure classes

Walk the questions in order and stop at the first "no".

| # | Class | Stage(s) | Diagnostic question | Owner |
| --- | --- | --- | --- | --- |
| 01 | Hallucination | Stage 4 | Is the atomic factual claim false? | Model / eval team |
| 02 | Instruction failure | Stage 2 | Did the trajectory obey every surviving constraint? | Prompt / policy / orchestration |
| 03 | Grounding failure | Stages 3-4 | Does the cited evidence support this exact claim, for this entity and version? | Retrieval / RAG |
| 04 | Formatting failure | Stage 5 | Can the downstream consumer parse and validate the payload? | Model interface / API contract |
| 05 | Tool failure | Stage 6 | Was the right tool called correctly, and was its actual result handled? | Agent orchestration / tool service |
| 06 | Integration failure | Stages 7-8 | Did the promised state exist exactly once, and become visible to the right user? | Application / platform / distributed systems |

One rule: walk in order. The first "no" is the primary root. Later failures are secondary symptoms.

## Truth × evidence matrix

Truth and evidence support are two independent axes.

| Truth | Evidence supported | Evidence unsupported |
| --- | --- | --- |
| True | No failure | Grounding failure only |
| False | Hallucination primary, retrieval/corpus secondary | Both labels |

Key principle: one incident gets one primary root label plus unlimited secondary labels.

## Adjudication rules for ambiguous cases

- False + unsupported: label both hallucination and grounding.
- True + unsupported: grounding only.
- False, faithfully copied from a bad retrieved source: retrieval or source-quality root, hallucination secondary.
- Right semantics but unparseable output: formatting is the operational root.
- Wrong tool or wrong arguments: tool failure.
- Valid tool call whose result is never persisted or displayed: integration failure.

If two labels are tied, choose the upstream one.

## Severity: consequence, not class

Severity depends on what changed, who authorized it, whether it can be undone, and how many users or records it touched.

| Level | Criteria | Examples |
| --- | --- | --- |
| Critical | Irreversible, unauthorized, wide blast radius | Unauthorized purchase, duplicate payment, legal filing, secret exposure, destructive production action |
| High | Reversible with effort, or acted on before detection | Consequential false advice, recoverable account changes |
| Medium | Contained, no external state changed | Recoverable wrong answers, failed actions with no side effect |
| Low | No decision or state affected | Cosmetic format or tone defects with no semantic loss |

Log severity independently from failure class. Keep a separate critical-failure count.

## Golden rules

1. Classify by the first invariant that broke.
2. One incident gets exactly one primary root label.
3. Unknown truth means unverified, not false.
4. False and unsupported are independent axes.
5. Tool failure ends at the tool boundary; integration failure starts after a valid tool success.
6. Severity comes from consequence, authorization, reversibility, and blast radius.
7. Never reflexively edit the prompt.
8. Every fix requires two regression tests: one narrow layer test and one end-to-end test.
