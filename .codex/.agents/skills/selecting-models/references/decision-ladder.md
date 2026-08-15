# Decision Ladder Reference

Supporting reference for the selecting-models skill.

## The six-step decision ladder

Apply in order. Never skip a step.

| Step | Name | Action | What breaks without it |
| --- | --- | --- | --- |
| 1 | Write the contract | Define tasks, inputs, outputs, tools, SLAs, and data constraints | The leaderboard winner solves the wrong job |
| 2 | Gate impossible options | Apply privacy, region, license, capacity, and tool-protocol vetoes | An unshippable model wins numerically |
| 3 | Measure the workflow | Collect quality, latency, cost, context, and tool evidence from real traffic samples | Provider claims become production assumptions |
| 4 | Normalize evidence | Map measurements to declared thresholds on a common scale | Incompatible units manufacture a winner |
| 5 | Expose weights | State which trade-offs the product values and test sensitivity | Preferences hide inside the spreadsheet |
| 6 | Route requests | Classify requests by risk, privacy, difficulty, and deadline into pools | One brittle winner serves everything |

## Measurement instruments per dimension

Every criterion must have a unit of measure and a measurement procedure. "Quality" is not a number; "critical-defect recall on a labeled holdout set" is a number.

## Vetoes are binary, not low scores

Model selection starts with impossible-option gates. Candidates that fail a veto do not enter the scoring matrix.

Common veto criteria include data residency, source-code retention, export-control region restrictions, license incompatibility, and capacity or availability constraints.

## Model variant identity

A model is a combination of four slots:

- checkpoint
- reasoning_mode
- chat_template
- tool_protocol

Changing any one without updating the others is a misconfiguration.

## Latency-relevant model-selection rules

A reasoning-tuned model at maximum effort is a hard veto if the latency budget is tight. Coding-tuned and tool-tuned checkpoints often outperform general benchmark winners for agentic workloads.

## Worked example targets

For repository-aware code review, define target quality, latency, cost, context, tools, and deployment constraints in your own contract.

## Routing policy structure

The final output of the decision ladder is a routing policy, not a single winner. Classify requests by risk, privacy, difficulty, and deadline, then pick from the eligible pool.
