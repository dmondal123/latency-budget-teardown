---
name: review-plan

description: Review a proposed plan against its original task for correctness, requirement coverage, evidence, dependency ordering, safety, completeness, and verifiability. Use when Codex needs to audit, validate, critique, approve, or improve an implementation plan, project plan, migration plan, remediation plan, operational runbook, or other multi-step approach before execution.
---

# Review Plan

Audit whether a plan is grounded, complete, executable, and capable of proving the requested outcome. Do not approve a plan merely because it is plausible.

## Establish the review basis

1. Identify the original task, constraints, success criteria, and non-goals.
2. Inspect relevant artifacts when claims depend on code, configuration, documentation, data, or current system state.
3. Mark claims as evidence, assumptions, or unknowns. Do not silently convert an unknown into an assumption.
4. If the original task is unavailable, review internal coherence but state that task alignment cannot be verified.
5. Scale review depth to risk. Keep low-risk reviews short; scrutinize security, migrations, destructive operations, concurrency, money, and production work.

## Build a coverage matrix

Map each requirement to both execution and verification.

Treat any requirement without an implementation step or verification method as incomplete. Detect plan steps that do not serve a requirement, risk control, or necessary dependency.

## Apply the review gates

- Goal: confirm the outcome and stopping condition are precise and observable.
- Evidence: confirm major decisions are supported by inspected facts.
- Approach: confirm every step contributes to the goal.
- Safety: check data loss, destructive actions, secrets, permissions, untrusted input, privacy, and external side effects.
- Completeness: check implementation, integration, configuration, migration, deployment, observability, documentation, and operations as applicable.
- Verification: connect every success criterion to a test, inspection, metric, or acceptance check.
- Executability: ensure another capable person could execute each step without guessing.

## Classify findings

- Critical: the plan can cause serious harm, targets the wrong outcome, or cannot achieve a core requirement.
- Major: a requirement, dependency, failure mode, or verification path is missing and should be fixed before execution.
- Minor: clarity, efficiency, or maintainability can improve without invalidating the approach.

## Produce the review

Lead with findings ordered by severity. For each finding include severity, affected requirement and plan step, unsupported assumption or omission, why it matters, and a concrete correction.

Then provide:

1. The requirement coverage matrix.
2. Open questions or assumptions.
3. One verdict: READY, REVISE, or BLOCKED.
4. A corrected plan when revision is useful and the missing information can be resolved from available context.

If there are no findings, say so directly and note any residual risk. Never equate checklist completion with proof: the plan is ready only when its claims are evidence-backed and its outcome can be verified.
