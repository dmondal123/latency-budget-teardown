# Effects, Approvals, and Audit Reference

Derived from `session25-guardrails-and-approval-boundaries_inference.md`.

## Effect record

Use project-native names, but represent at least:

```yaml
effect:
  action: git push origin fix/oauth
  cwd: /workspace/repo
  targets: [remote: origin, branch: fix/oauth]
  scope: repository
  reversibility: persistent_remote
  externality: network_write
  secrets: none
  duration: bounded
  side_effect_class: recorded
  permissions: [network:git-origin]
```

Resolve targets before classification. Preserve the original proposal for audit, but let policy consume the normalized effect.

## Classification

| | Reversible | Irreversible or persistent |
|---|---|---|
| Local | Usually `ALLOW` when bounded and recoverable | `ASK` |
| External | `ASK` | `ASK` |

Apply hard overrides before the grid:

- secret extraction or credential disclosure → `DENY`;
- out-of-scope target or prohibited production access → `DENY`;
- action explicitly disallowed by organizational policy → `DENY`.

Adjust the grid for the system's threat model. Keep the three outcomes distinct so humans see only legitimate judgment calls.

## Approval request and grant

Display and record the exact command/tool call and arguments, resolved target and working directory, expected effects and reversibility, requested permissions, one-shot or session lifetime, and matching policy rule.

A one-shot grant must close after the exact action. A session grant must match a narrowly defined capability, remain visible, support immediate revocation, and never be inferred from a narrow yes.

## Completion event

```yaml
result:
  status: completed # completed | failed | declined
  action_id: act_123
  grant_id: grant_456
  observed_effects: [remote_branch_updated]
  error: null
```

Approval is not an observed effect. Only `completed` proves that the action happened.

## Tests

- Attempt execution through every tool adapter and assert all routes hit the gate.
- Wrap a dangerous command in scripts, aliases, or alternate syntax and assert the same effect classification.
- Deliberately misclassify an action as allowed and assert the sandbox still blocks excess access.
- Attempt reads of credentials and assert hard denial without a human prompt.
- Verify one-shot grants cannot authorize a second action.
- Verify session grants are listed and revocable.
- Simulate decline, remote rejection, partial failure, and success; assert distinct factual outcomes.
- Measure approval-prompt volume and false-positive prompts to detect fatigue.
