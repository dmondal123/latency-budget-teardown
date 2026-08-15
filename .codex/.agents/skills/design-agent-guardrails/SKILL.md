---
name: design-agent-guardrails
description: Use when designing, implementing, auditing, or reviewing guardrails and human-approval boundaries for tool-using agents.
---

# Design Agent Guardrails

Route every proposed action through one enforceable path. Grant narrow capabilities, not general trust, and make the model observe what actually happened.

## Build the six rungs in order

1. **Funnel:** create exactly one path from proposed tool intent to execution. Make bypasses impossible and log every verdict at this choke point.

2. **Describe:** resolve the target and compute a structured effect before policy runs. Include scope, reversibility, externality, secret exposure, duration, and side-effect class. Judge consequences, not command spelling.

3. **Bound:** enforce filesystem, network, environment, and resource permissions in the runtime. Keep credentials and unrelated paths outside the reachable boundary even if policy misclassifies the action.

4. **Classify:** return exactly one of `ALLOW`, `DENY`, or `ASK`. Auto-allow bounded reversible local actions; hard-deny prohibited capabilities such as secret extraction; request approval for legitimate consequential actions.

5. **Approve:** show the exact action, resolved targets, working directory, permissions, effect, and grant lifetime. Bind a one-shot grant to that displayed capability. Make wider session grants explicit, visible, revocable, and separately chosen.

6. **Observe:** execute inside the granted sandbox, then report `completed`, `failed`, or `declined`. Feed the real result—not the approval event—back into planning.

## Audit the design

Trace every tool implementation to the single executor; treat any alternate path as a critical bypass.

Test policy on semantically equivalent commands and wrapper scripts to ensure it consumes effects rather than raw strings.

Verify sandbox denial independently of policy decisions.

Confirm forbidden actions are never offered for approval.

Confirm harmless reads do not generate prompts that train users to click through.

Confirm a narrow approval cannot silently become a session-wide grant.

Confirm decline and execution failure leave the model believing that no side effect occurred.

Tie each added rule to a named failure or threat; remove redundant prompts that add fatigue without new protection.

Read [references/effects-approvals-and-audit.md](references/effects-approvals-and-audit.md) for effect fields, classification guidance, approval records, and adversarial tests.

## Deliver

Produce an execution-path diagram, typed effect and verdict schemas, runtime permission profiles, policy table, approval request/grant formats, revocation mechanism, completion event schema, and bypass/adversarial test suite.
