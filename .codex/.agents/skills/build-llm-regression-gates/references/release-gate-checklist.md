# Release Gate Checklist
Derived from `session21-regression-tests-for-llms-and-agents_inference.md`.

## Systems that answer

1. Name every confirmed bug with a permanent case and expected action.

2. Grade outcome independently from wording; make hard failures vetoes.

3. Freeze code, prompt, corpus, model, grader, config, cache, and result provenance.

4. Pair candidate and baseline by case before aggregating.

5. Calibrate judges against humans and test bias.

6. Repeat trials and bootstrap paired case deltas for an interval.

7. Predeclare and report risk, intent, locale, and failure-mode slices.

8. Encode risk appetite as an ordered gate written before results are viewed.

9. Limit exposure with canary tripwires and rollback.

10. Convert adjudicated production incidents into owned cases.

## Systems that act

11. Grade complete episodes by target end state.

12. Reset an isolated world and fake all side effects for every trial.

13. Assert required/forbidden actions and tool arguments; constrain order only when semantically required.

14. Run repeated trials and report both `pass@k` and `pass^k`.

15. Gate steps, cost, and latency per task class alongside success.

16. Attribute failures to recorded retrieval, planning, model, tool, or budget spans.

17. Gate irreversible actions and approvals independently of task-success averages.

18. Use shadow mode, canary, kill switch, and confirmed-incident replay.

## Statistical cautions

Compare within-case paired outcomes, never two independent aggregate averages.

Resample paired cases together; do not independently bootstrap baseline and candidate rows.

Preserve task-level grouping when multiple trials belong to one task.

Treat intervals as uncertainty summaries under the chosen sampling assumptions, not universal guarantees.

Predeclare protected slices; post-hoc subgroup hunting is exploration, not release evidence.

## Gate order

1. Missing or invalid evidence: `BLOCK` or explicit `REVIEW`.

2. Forbidden action, approval breach, or safety veto: `BLOCK`.

3. Protected-slice regression beyond its budget: `BLOCK`.

4. Overall quality interval outside budget: `BLOCK`.

5. Cost or latency outside its budget: `BLOCK`.

6. Offline pass with residual live uncertainty: `CANARY`.

7. Canary stable for the declared window with no tripwire: `SHIP`.

Never average across these branches.

## Rollout contract

Define shadow duration and disabled side effects, initial canary percentage, hard tripwires, promotion window, rollback target, a kill switch that degrades safely, and the incident fields needed to replay the starting world and trajectory.
