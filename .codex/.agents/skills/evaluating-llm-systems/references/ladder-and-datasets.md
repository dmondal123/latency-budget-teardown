# Ladder and Datasets Reference

## The eval-first shift

Vibes-driven workflow:

change the prompt, run a few examples, ship. Evidence lives in someone's memory.

Eval-first workflow:

change the prompt, run the frozen suite, compare to baseline, let the gate decide. Evidence lives in a rerunnable record.

An eval is a written behavioral contract, a named input distribution, an oracle per criterion, and a rerunnable versioned record.

It is not a benchmark score, a leaderboard position, a model-provider metric, or a folder of prompts run once before a demo.

## The 9-mechanism ladder

Three phases:

- Rungs 1-4: specification
- Rungs 5-7: apparatus
- Rungs 8-9: control loop

| Rung | Mechanism | What it adds | Without it | Often skipped? |
| --- | --- | --- | --- | --- |
| 1 | Draw the behavioral boundary | Versioned task contract (`may` / `must_not`) | Assistant solves the wrong task convincingly | Yes, most impactful skip |
| 2 | Split "good" into dimensions | Named quality vector, including latency and cost | Blended score hides regressions | No |
| 3 | Turn harms into vetoes | Boolean fatal gates | Rare catastrophic failure is averaged away | Yes |
| 4 | Set the bar before seeing candidates | Frozen thresholds with freeze date and owner | The bar moves toward the preferred candidate | Yes, most impactful skip |
| 5 | Recreate the traffic | Named slices plus a sealed holdout | Happy-path suite passes while prod fails | No |
| 6 | Give every criterion an oracle | Code, model, or human grader, calibrated and versioned | Criteria without graders are wishes | No |
| 7 | Make the contract executable | Harness with raw output, scores, evidence, and stamps | Comparisons are manual and cherry-picked | No |
| 8 | Make every change earn promotion | CI release gate | A change fixes one demo and degrades another slice | Yes |
| 9 | Feed reality back | Incident minimize, add case, rerun full suite | The same failure class recurs | No |

## Rung 1: draw the behavioral boundary

Write the `may` and `must_not` contract before any prompt work. Version it so boundary changes are visible in diffs.

## Rung 4: freeze thresholds before candidates

Use frozen thresholds such as:

```python
accept = (
    fatal_count == 0
    and groundedness >= 0.95
    and resolution >= 0.85
    and p95_latency_ms <= 1800
    and cost_per_reply <= 0.02
)
```

Commit thresholds with a freeze date and owner. Do not edit them in the same review as the implementation change.

## Rung 8: make every change earn promotion

Run the gate in CI on every prompt, model, retrieval, or tool change. A prompt edit counts as a production change.

## Building eval datasets

- Sample from real production logs.
- Redact sensitive fields; do not paraphrase them.
- Start with 48-60 cases and grow from production.
- Tag each case with exactly one slice family: typical, edge, adversarial, or ambiguous.
- Keep one holdout set that development never tunes against.

## Quality vector table

Include latency and cost in the same evidence row as quality scores.

| Dimension | Cheapest oracle that can decide it |
| --- | --- |
| Schema validity | Code |
| Action safety | Code |
| Privacy / PII preservation | Code |
| Latency | Code timer in harness |
| Cost per request | Code token counter |
| Groundedness | Model judge plus reference; calibrate k |
| Tone and style | Model judge; calibrate k |
| Relevance and coherence | Model judge; calibrate k |
| Task fidelity / resolution | Model judge or human sample |
| Helpfulness / subtle policy judgment | Human sample |

## Glossary

Include definitions for task contract, quality vector, fatal gate, threshold, slice, assurance set, grader, calibration, harness, baseline, release gate, and minimization.

## Ten-day adoption path

1. Write the task contract.
2. Name the quality dimensions.
3. List the fatal failures.
4. Freeze thresholds.
5. Build 40-60 cases across named slices.
6. Wire graders.
7. Run the harness on today's system.
8. Put the gate in CI.
9. Wire the production loop.
10. Feed incidents back into the suite.
