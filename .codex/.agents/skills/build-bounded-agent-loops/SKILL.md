---
name: build-bounded-agent-loops
description: Use when designing, implementing, testing, or reviewing finite, observable agent loops with bounded steps, retries, budgets, state growth, delegation, and typed termination.
---

# Build Bounded Agent Loops

Make the loop—not the model—own termination, retries, state growth, side effects, and failure reporting. State the worst case before the first tool runs.

## Implement the control flow

```typescript
while (state.steps < cfg.maxSteps) {
  const action = await decide(state.messages)
  state.steps += 1
  const result = await withRetry(action, cfg.maxRetries)
  state = observe(state, action, result)
  const stop = terminal(state)
  if (stop) return { stopReason: stop, state }
}

return { stopReason: "step_limit", state }
```

Preserve these phase boundaries:

1. Gate decisions with pure policy.
2. Let `decide` return exactly one action or one explicitly bounded batch.
3. Increment steps on the decision before any I/O.
4. Keep all side effects and retry behavior inside execution.
5. Make `observe` the only state writer and append only the final result of an action.
6. Make `terminal(state)` pure. Let the model propose completion, but verify success from state.
7. Return every expected outcome as a typed stop reason; reserve exceptions for programmer errors.

## Bound retries and state

Count a retry as another attempt of the same decision, not another step.

Retry only transient faults such as timeouts, resets, 429s, and appropriate 5xx responses.

Treat validation errors, bad arguments, and failed tests as results, not retryable transport faults.

Retry non-idempotent writes only with an idempotency key; otherwise mark them non-retryable.

Cap retry wall time and log it independently from token cost.

Truncate observations at the observe boundary while preserving the full raw transcript for audit.

## Define termination

Check in this order: verified success, unrecoverable tool failure, repeated-state/no-progress, then step exhaustion. Extend the closed union explicitly for budget exhaustion or cancellation. Return enough state for safe inspection or resumption.

## Test and tune

Unit-test gate, observe, and terminal without a model or network.

## Define termination

Check in this order: verified success, unrecoverable tool failure, repeated-state/no-progress, then step exhaustion. Extend the closed union explicitly for budget exhaustion or cancellation. Return enough state for safe inspection or resumption.

## Test and tune

Unit-test gate, observe, and terminal without a model or network.

Use scripted fake tools to verify exact attempt counts and retry classes.

Assert step, attempt, message, and stop-reason invariants on every return.

Sweep step and retry budgets independently. Derive `maxSteps` from the task-class step distribution (start with p95 plus one) and retries from measured transient failures.

Log unused headroom and stop-reason ratios. Diagnose the reason before increasing any budget.

Read [references/loop-invariants-and-extensions.md](references/loop-invariants-and-extensions.md) for formulas, stop semantics, safe extensions, and code-review anti-patterns.

## Deliver

Provide the loop implementation, closed stop-reason type, retry classifier, invariant tests, worst-case arithmetic, exit-event schema, budget-tuning evidence, and caller behavior for every stop reason.

