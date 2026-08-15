# Loop Invariants and Extensions

Derived from `session24-building-a-bounded-agent-loop_inference.md`.

## Core state and stop reasons

```typescript
type AgentState = {
  messages: Message[]
  steps: number
  attempts: number
}

type StopReason =
  | "succeeded"
  | "step_limit"
  | "tool_failure"
  | "no_progress"
  | "budget_exceeded"
  | "cancelled"
```

For the minimal one-action loop with one initial task message and one observation per completed step:

```text
steps <= maxSteps
attempts >= steps
attempts <= steps * (maxRetries + 1)
messages <= 1 + 2 * steps
stopReason != null on every return
```

If compaction, batching, or suspension changes an equality, replace it with a documented bound and test that bound.

## Worst-case arithmetic

```text
model calls <= maxSteps
tool calls <= maxSteps * maxParallel * (maxRetries + 1)
spend <= the configured token/currency ceiling
depth <= maxDepth, with child budgets deducted from the parent
```

Do not ship an extension that cannot add a finite term to this block.

## Stop semantics

| Reason | Meaning | Caller action |
|---|---|---|
| `succeeded` | Goal predicate verified | Accept artifact |
| `step_limit` | Partial work, next decision denied | Inspect; resume only deliberately |
| `tool_failure` | Environment/action failed unrecoverably | Alert; do not blindly auto-resume |
| `no_progress` | Meaningful state fingerprint repeated | Change strategy or escalate |
| `budget_exceeded` | Spend ceiling reached | Review partial work |
| `cancelled` | External cancellation | Exclude from model-failure metrics |

Check success before failure/stall so success on the last permitted step remains success. Check tool failure before stall so an unchanging broken tool is not mislabeled `no_progress`.

## Safe extensions

Token/currency budget: gate before decisions and after observation; add `budget_exceeded`.

Parallel tools: bound batch size; use one observation block per batch.

Context compaction: retain raw transcript; document message-count bounds.

Sub-agents: model them as bounded calls, cap depth, and deduct child budgets from the parent.

Human approval: serialize state and represent waiting as suspension, not success or failure.

Cancellation: check at loop boundaries and between retries; never abandon an in-flight non-idempotent write.

## Reject in review

Wall-clock timeout used instead of a step bound.

Step increment after tool I/O.

Unbounded multiple actions per model turn.

Model-emitted `done` trusted as success.

Blanket retry on non-zero exit.

Retry of a non-idempotent write without a key.

Raw unbounded tool output appended to context.

More than one state writer.

No repeated-state fingerprint.

Expected terminal outcomes thrown as exceptions.

Fresh budgets granted to nested agents.

## Exit event

Emit run ID, task class, stop reason, steps/maxSteps, attempts/retries, messages, input/output tokens, wall/tool time, spend, and unused headroom on every exit. A dashboard should answer stop-reason distribution, median headroom, and safe-resume policy without log inspection.

