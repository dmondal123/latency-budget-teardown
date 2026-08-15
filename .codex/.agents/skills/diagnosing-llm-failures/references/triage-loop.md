# Triage Loop

## The 8-step loop

When something goes wrong in production, contain first, specify before reading the trace, and only fix the layer that actually broke.

1. Contain
2. Reproduce
3. Specify
4. Replay
5. Localise
6. Label
7. Repair
8. Regress

## Step 1 — Contain

Disable writes and retries. Revoke credentials if abused. Preserve logs and traces before rotation. Reconcile external state and reverse it where needed.

## Step 2 — Reproduce

Capture the full reproduction bundle:

- prompt and policy version
- retrieval index snapshot
- model snapshot
- tool schema
- dependency lockfile
- application build

If any one element is missing, the reproduction is a guess.

## Step 3 — Specify

Write the expected invariant at each of the eight pipeline stages before reading the trace. Do not look at the trace until all eight invariants are written.

## Step 4 — Replay

Walk the trace from input to user-visible state, layer by layer. Note what was expected and what was observed at each stage.

## Step 5 — Localise

Find the first expected/observed divergence. That divergence is the root cause. Every later failure is a secondary symptom.

## Step 6 — Label

Record:

- primary root
- secondary symptoms
- domain invariant
- severity
- blast radius

## Step 7 — Repair

Fix the layer that broke. Do not reflexively edit the prompt. If the break was at the schema layer, fix the contract. If it was at the tool layer, fix orchestration or the tool service. If it was at app state or outcome, fix idempotency and rendering.

Only edit the prompt if Stage 2 or Stage 4 is the confirmed primary root.

## Step 8 — Regress

Add two tests:

- a narrow layer-specific test
- an end-to-end test

Both are required.

## Why each critical step matters

If you skip containment, blast radius grows. If you skip the reproduction bundle, root cause is a guess. If you read the trace first, you anchor on the last symptom. If you fix the last symptom, you relocate the bug one stage to the right. If you skip both regression tests, you cannot verify the fix or localize the next regression.

> Classify an incident by the first invariant that broke, not the last symptom the user saw.
