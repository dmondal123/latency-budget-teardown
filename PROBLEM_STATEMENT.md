Topics: 8, 12, 2 — Users say the feature "feels slow." Instrument an end-to-end pipeline (retrieval + model + validation is enough), produce p50/p95 waterfall breakdowns, then set an explicit latency budget per stage. Apply at least two interventions — streaming, parallel calls, max_tokens tuning, caching — and show measured deltas against the budget. Week shape: D1–2 instrument + baseline · D3–4 interventions · D5 budget doc.

Criterion	Weight	A 4/4 looks like
Measurement quality	25%	Waterfalls at p50 and p95 with enough samples to be stable; tail behavior analyzed separately from median.
Intervention rigor	25%	Each change measured in isolation; quality side-effects of latency fixes (e.g., tighter max_tokens) checked, not assumed away.
Budget judgment	25%	The per-stage budget is defensible from user-experience grounds (perceived vs. total latency); explicitly states which stage gets cut first under pressure.
Universal grading criteria
Universal criteria — 25% of every grade, identical across all 27 rubrics:

Criterion	Weight	A 4/4 looks like
Professional baseline	15%	Repo with README; one command reproduces every number and chart; model versions and deps pinned; all metrics produced by scripts, never hand-copied; total spend (tokens + dollars) reported.
AI-collaboration log & communication	10%	A log of how you directed Claude Code/Codex, including at least two places the agent was wrong or suboptimal and how you caught it; a final writeup ≤2 pages that a staff engineer would forward. Analysis that reads as unedited model output scores 0 here.
Submission requirements
Upload one .zip archive of the complete codebase through the file-submission task below. The archive must include the README, pinned dependency/lock files, reproducible scripts, tests, generated metrics/charts, the AI-collaboration log, and the final write-up (maximum two pages).

Do not include secrets, API keys, credentials, .env files, dependency caches, virtual environments, node_modules, or generated build folders. The archive must be a real ZIP file and should stay below 500 MB uncompressed.