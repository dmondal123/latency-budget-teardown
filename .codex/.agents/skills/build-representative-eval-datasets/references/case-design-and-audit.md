# Case Design and Audit Reference

Derived from `session19-building-high-quality-evaluation-datasets_inference.md`.

## Four-block case

```yaml
id: expense.edge.missing-date.001

type: edge

task: "Please reimburse this parking receipt."

world:
  receipt: parking-no-date.jpg
  transaction_date: null
  policy: expense-policy@v7
  clock: 2026-08-15T10:00:00+05:30

oracle:
  outcome: ask for the missing transaction date
  required: [request_transaction_date]
  forbidden: [create_draft, submit_reimbursement]
```

Accept a case only when a colleague can run it and reach the same verdict without asking for context.

## Eight-layer order

1. One common case: prove the harness and oracle can fail.

2. Normal traffic: reproduce intent mix and real phrasing.

3. World state: pin documents, records, policy, permissions, clock, and tool responses.

4. Edge cases: bend one legitimate assumption per case.

5. Adversarial cases: cover every surface the system reads, including grader inputs.

6. Regression cases: preserve escaped defects verbatim and permanently.

7. Trace grading: inspect actions, arguments, approvals, and state—not only prose.

8. Production loop: mine incidents, low-confidence traces, and model disagreement on a fixed cadence.

## Starting coverage budget

Use these as planning defaults, then adjust to actual traffic and risk:

| Type | Starting share |
| --- | --- |
| Normal | 50–60% |
| Edge | 20–25% |
| Adversarial | 10–15% |
| Regression | Uncapped |

Do not force regressions under a percentage cap. Add risk-weighted minimums for protected slices even when their traffic share is small.

## Static checks

Require non-empty `task`, `world`, and `oracle` fields.

Require `oracle.outcome`, `oracle.required`, and `oracle.forbidden`.

Require pinned policy and fixture versions.

Reject live-service dependencies and implicit current time.

Require an owner and source incident for regression cases.

Verify adversarial payloads occur outside `user_turn`.

Compare case-type proportions with the declared coverage budget.

Require tool arguments and post-state checks for consequential actions.

## Suite smells

Treat three or more as an urgent dataset-quality warning:

- Pass rate has never decreased.
- No case expects the system to refuse, ask, or do nothing.
- Cases have no frozen world state.
- Every adversarial payload appears only in the user turn.
- A recent incident has no permanent case.
- The grader reads only the final message.
- Nobody can name an uncovered production shape.

## Production intake

For each signal, first adjudicate whether the behavior was wrong. Then minimize the trace, redact sensitive content, freeze the exact world and policy, assign an owner, add the case, and rerun the full suite. Raw logs are leads, not labels.
