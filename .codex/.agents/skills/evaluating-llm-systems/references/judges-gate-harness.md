## Judges, Gates, and Harness Reference

### LLM-as-judge

Use code first. Escalate to an LLM judge only when a code assertion cannot express the criterion.

| Grader | Best for | Strengths | Limits |
| --- | --- | --- | --- |
| Code | Schema validity, forbidden actions, PII patterns, latency, cost | Deterministic, fast, auditable | Only works where correctness is mechanically expressible |
| Model judge | Groundedness, tone, coherence, relevance, rubric scoring | Scales to large sets, handles open-ended text | Must be calibrated against human labels; position and verbosity bias |
| Human | Helpfulness, subtle policy judgment, ground-truth labeling | Highest authority | Slow and costly; use on a sampled subset and for calibration |

### Calibration protocol

Before any judge gates anything:

1. Label a sample of outputs by hand.
2. Run the judge on the same sample.
3. Compute Cohen's kappa against the human labels.
4. Publish agreement alongside every suite run.
5. Re-check after any change to the judge prompt or model.

### Documented biases

- Position bias: the judge prefers whichever answer appeared first. Fix by randomizing candidate order.
- Verbosity bias: the judge prefers the longer answer. Address it explicitly in the judge prompt.

### Grader versioning

Store `grader_version` next to every score so grader changes are separable from model changes.

### Scoreability rule

A specification that is readable but not consistently scorable is not an eval. Ban the word "accuracy"; require a specific dimension name.

### Fatal gates

Harms cannot be averaged. If privacy is 15% of a blended score, a system can leak card digits on one case in twenty and still clear a high bar. Fatal gates must be pure `(input, output) -> bool` checks that hard-block the whole run.

### Gate list discipline

Keep the gate list short. A gate that fires on ordinary imperfection will be disabled. Log the offending span and monitor gate firing rates.

### Promotion predicate

Example:

```python
accept = (
    fatal_count == 0
    and groundedness >= 0.95
    and resolution >= 0.85
    and p95_latency_ms <= 1800
    and cost_per_reply <= 0.02
    and no_slice_regresses(baseline, tolerance=0.02)
)
```

### Harness engineering

Persist every run with:

- `run_id`
- `case.id`
- `raw_output`
- full `scores`
- `evidence`
- `grader_version`
- `model_id`
- `prompt_hash`
- `retrieval_index_snapshot`

Raw output is mandatory so a run can be re-graded later.

### CI requirement

Treat prompt hashes as production changes. Run the full gate in CI on every diff touching prompts, model selection, retrieval config, or tools.

### Frozen thresholds

Commit thresholds with a freeze date and named owner before candidates are run. Threshold changes must land in a separate PR.

### Incident closure

Minimize the failing input, assign it to the correct slice, add it to the eval set, and rerun the full suite.

### Quarterly slice review

Review slice composition quarterly against actual production traffic mix. The assurance holdout reveals what development iteration never tested.

### Reliability layers

- Layer 1: compute one absolute deadline at admission and derive per-attempt timeouts from the remaining budget.
- Layer 6: hash all seven inputs that determine model behavior and store `contract_hash` on every eval result row.
- Layer 7: promote through evidence; keep the previous contract warm so rollback is a pointer flip, not a deployment.
- Layer 8: log per span, including `gate.wait_ms`, `provider.latency_ms`, `attempt.n`, and `contract.hash`.
