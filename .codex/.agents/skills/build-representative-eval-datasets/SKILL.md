---
name: build-representative-eval-datasets
description: Use when building, reviewing, or expanding representative evaluation datasets for LLM or agent systems.
---

# Build Representative Eval Datasets

Treat every score as a claim about the sampled dataset, not the system in general. Prefer a smaller reproducible suite with explicit blind spots over a large collection of vague prompts.

## Build the suite

1. Define the behavioral boundary and the production population the score should represent.

2. Start with one common task and write its oracle before running the system. Deliberately break the system once to prove the case can fail.

3. Store every case as a versioned file with four blocks:

   - `task`: preserve the user's natural wording.
   - `world`: freeze documents, records, permissions, policy version, time, and tool responses.
   - `run`: capture the complete trajectory, including tool arguments, approvals, and handoffs.
   - `oracle`: state the expected outcome plus required and forbidden events.

4. Add layers in order: normal traffic, world-state variants, single-perturbation edge cases, adversarial cases across every input surface, permanent regressions, trace grading, then a production feedback loop.

5. Sample normal intents roughly in traffic proportion. Preserve typos, ambiguity, locale, and other real distribution features.

6. Derive each edge case from a passing normal case by bending exactly one assumption. Include cases where the correct behavior is to ask, refuse, or do nothing.

7. Place adversarial payloads in retrieved documents, tool output, policy sources, and grader-facing content—not only in the user turn. Include at least one attack on the grader.

8. Convert every confirmed incident into a minimized, owned regression case while the exact bytes and world state still exist. Never delete it after the fix ships.

9. Grade trajectories as well as final messages. Assert tool names and arguments, required approvals, forbidden side effects, and resulting state.

10. Report coverage and failures by case type, intent, risk, locale, and failure mode. State known gaps beside the pass rate.

## Review the result

Reject cases that require unstated context or subjective “looks right” judgments.

Reject live data, floating policy references, or calls to `now()` that make reruns differ.

Investigate a suite that stays at 100% while new layers are added; falling pass rate can indicate improved coverage.

Keep hard harms as vetoes. Never allow a favorable aggregate to offset a forbidden event.

Review relaxed expectations like schema changes and require an approver.

Read [references/case-design-and-audit.md](references/case-design-and-audit.md) for the case schema, coverage budget, layer checklist, and suite-smell audit.

## Deliver

Return or create a versioned case schema and case files, a coverage table by declared slice, trace-aware oracles, known coverage gaps, and a production-to-regression intake process with owners.
