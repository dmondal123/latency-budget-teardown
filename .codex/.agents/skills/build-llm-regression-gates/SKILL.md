---
name: build-llm-regression-gates
description: Use when evaluating LLM or agent changes against a trusted baseline with reproducible regression evidence, release gates, stochastic trials, risk slices, or staged rollout controls.
---

# Build LLM Regression Gates

Treat a release gate as versioned code that maps frozen evidence to `BLOCK`, `CANARY`, or `SHIP`. Write the decision rules before viewing candidate results.

## Build the evidence chain

1. Convert each confirmed failure into a permanent named case with fixed input, fixture, expected action, source incident, and owner.

2. Separate hard outcome checks from soft quality metrics. Make safety, policy, forbidden-action, and protected-slice failures absolute vetoes.

3. Freeze the run identity: code SHA, prompt hash, provider and model version, corpus/policy version, resolved config, grader versions, cache setting, and output artifact.

4. Run candidate and trusted baseline on identical cases and trials. Join by case ID before calculating candidate-minus-baseline deltas.

5. Repeat stochastic trials. Report a paired confidence interval, not only a point estimate, and preserve pairing while resampling cases.

6. Predeclare slices such as risk, intent, locale, and failure mode. Compute deltas and intervals per slice; never allow aggregate gains to erase a protected-slice loss.

7. Calibrate model judges against blind human labels and test known biases before allowing judged metrics into a gate.

8. Encode ordered decision rules and make CI own the exit status. Evaluate hard vetoes before trade-off budgets.

9. Permit live exposure only after the offline gate passes. Start with a small canary, explicit tripwires, a stable promotion window, and tested rollback.

10. Feed confirmed production incidents back into the permanent suite after adjudication and privacy review.

## Extend the unit for agents

1. Test an episode: task plus frozen starting world, trajectory, and final world state—not the final reply.

2. Restore a byte-identical disposable sandbox for every trial and replace external side effects with recording fakes.

3. Assert required and forbidden tools, arguments, meaningful ordering, approvals, and end state.

4. Report `pass@k` for capability and `pass^k` for reliability; gate safety-critical work on consistent success.

5. Measure steps, cost, and latency per task class and relate them to success. Do not accept an efficiency gain that cuts off a required safety path.

6. Trace failures to retrieval, planning, tool execution, or budget spans.

7. Classify irreversible actions separately and require their action-specific approvals.

8. Roll out through shadow mode, canary, armed kill switch, and incident replay.

Read [references/release-gate-checklist.md](references/release-gate-checklist.md) for the 18-mechanism audit, gate ordering, statistics cautions, and rollout requirements.

## Deliver

Create a frozen manifest, baseline/candidate results joined by case, overall and per-slice paired intervals, coded gate policy, CI decision, staged rollout plan, and a closed incident-to-regression loop.
