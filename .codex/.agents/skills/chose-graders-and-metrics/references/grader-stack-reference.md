# Grader Stack Reference

Derived from `session20-choosing-graders-and-metrics_inference.md`.

## Selection matrix

| Layer | Reads | Output | Authority | Primary blind spot |
| --- | --- | --- | --- | --- |
| Invariant | tool name, arguments, result, post-state | boolean | hard gate | qualities not encoded in trace/state |
| Similarity | answer and reference embeddings | float | closed label | truth, negation, omission, deception |
| LLM judge | answer, rubric, supplied evidence | calibrated quality gate | hidden | missing evidence and model bias |
| Human | same evidence and all signals | rubric, judge label: `PASS`/`REVIEW`/`BLOCK` | audit/adjudication | cost and sampling limits |

## Invariant pattern

Check call validity, exact tool and arguments, forbidden events, and final state separately. “Call issued” is not equivalent to “action happened.” Keep free-text output out of this layer.

## Similarity protocol

1. Label examples before inspecting scores.
2. Choose and pin an embedding model version.
3. Fit an explicit threshold on the labeled set.
4. Test paraphrases, negation pairs, wrong identifiers, premature status claims, and verbose non-answers.
5. Route low-confidence scores; never use similarity alone to pass or block.

## Judge protocol

Use a closed label set such as `PASS | FAIL | UNKNOWN`.

Define one observable criterion per rubric item.

Include all required evidence, including trace and post-state when the rubric asks about truth.

Grade one candidate per call.

Pin model, prompt, sampling settings, and rubric version.

Measure order stability, verbosity bias, and self-preference where applicable.

## Human audit

Use at least two trained raters, blind to judge labels, on a stratified sample. Over-sample judge `PASS`es and protected slices. Report `κ_hh` (human-human agreement) before `κ_jh` (judge-human agreement).

Do not treat any fixed kappa threshold as universal. The session uses `κ_hh ≥ 0.70` and `κ_jh ≥ 0.60` as worked-example gates, not laws.

## Ordered policy

```js
function decide(data, threshold) {
  if (data.exact === 0) {
    return { label: 'BLOCK', detail: 'hard invariant failed' };
  }

  if (data.human != null && data.human !== data.judge) {
    return { label: 'REVIEW', detail: 'human-judge disagreement' };
  }

  if (data.semantic < threshold || data.judge === 0) {
    return { label: 'BLOCK', detail: 'quality gate failed' };
  }

  return { label: 'PASS', detail: 'all gates satisfied' };
}
```

Test branch order explicitly. Store this logic beside grader definitions, not in a spreadsheet.

## Readiness checks

- Invariants inspect trace and post-state.
- Similarity threshold is explicit and metric regression cases exist.
- Judge rubric and evidence schema are versioned.
- Human raters are blind and agreement is reported in the correct order.
- Hard gates run first and cannot be outvoted.
- `REVIEW` exists and is operationally consumed.
- Every known bad-answer type has a first-catching layer.
