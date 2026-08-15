# AGENTS.md

Repo rules for Codex and other agents working in this workspace.

## Working rules

- Treat this repo as documentation plus tooling scaffolding unless a file explicitly says otherwise.
- Prefer deterministic, reproducible scripts over hidden automation.
- Do not write into `.git/`, `.codex/` internals, or generated outputs unless a task explicitly requires it.
- Do not use destructive git commands.
- Keep changes small and reviewable.
- Commit every completed feature or fix promptly in a small, self-contained commit; do not defer unrelated completed work. Make follow-up commits whenever a coherent change, test, or correction is ready for review.
- Use a short Conventional Commit subject: `type(scope): imperative summary` (for example, `docs(agents): clarify tool-use policy`). Include validation command(s) in the body only when they are not self-evident.
- Before every commit, run `/status` and record the reported token use and model in `COLLABORATION_NOTES.md` only when the commit or session produced a significant decision, correction, failure investigation, or learning.

## Core documentation

Read the smallest relevant set of these documents before changing the corresponding area. The [problem statement](PROBLEM_STATEMENT.md) is authoritative; plans and logs do not override it.

| Document | Use it for |
| --- | --- |
| [README.md](README.md) | Project purpose, current state, and reproduction contract |
| [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) | Authoritative assignment requirements and acceptance criteria |
| [RAG_PIPELINE_PLAN.md](RAG_PIPELINE_PLAN.md) | Approved pipeline, evaluation, latency, and model plan |
| [PROGRESS.md](PROGRESS.md) | Milestones, gates, risks, and next actions |
| [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) | Pre-registered experiments and measured evidence |
| [COLLABORATION_NOTES.md](COLLABORATION_NOTES.md) | Human/AI decisions, corrections, and learnings |
| [TASKS.md](TASKS.md) | Task sequence and current work items |
| [AGENTS.md](AGENTS.md) | Repository operating rules |

## Collaboration and tool budget

- Use parallel agents only for two or more independent, read-safe or disjoint-file tasks whose results can be merged without ordering dependencies. Assign each agent explicit ownership and keep one agent responsible for integration and validation.
- Keep sequential work sequential when tasks share files, modify the same symbols, depend on earlier results, or require a single coherent decision.
- Enable skills and MCPs selectively for the current task; disable or avoid unused integrations. Prefer a deterministic local CLI when it provides the needed capability.
- Keep at most **three MCP servers active** at any time, including any needed by subagents. Treat this as an ongoing operating limit, not a one-time setup step.

## Project logs

- `COLLABORATION_NOTES.md` is a concise reflection log, not a transcript or per-task journal. Add an entry only for a significant human decision, agent error or suboptimal approach, failed investigation, changed direction, or reusable learning. Each entry should state the context, what changed or was learned, evidence, and—when it followed a commit—the `/status` token use and model. If nothing significant happened, do not update the file.
- `EXPERIMENT_LOG.md` starts when RAG-pipeline building and benchmark execution start. Until then, leave it empty or use only a short “not started” placeholder. Once experiments begin, record pre-registered conditions, commands, raw evidence, and measured decisions; do not use it for plans, estimates, or routine progress updates.

## Validation

- Prefer cheap, external checks for any change: lint, tests, or a focused script.
- If a change introduces a wrapper or script, verify the command path end to end.
- Until the RAG implementation adds its test runner, validate documentation with focused structure, link, secret, and reproducibility checks.

## Project requirements

The authoritative task requirements are in `PROBLEM_STATEMENT.md`. Keep all implementation and documentation aligned with these requirements:

- Instrument an end-to-end retrieval → model → validation pipeline.
- Produce reproducible p50 and p95 waterfall breakdowns, with enough samples to assess tail behavior separately from the median.
- Assign a defensible latency budget to every stage, including which stage is cut first under pressure and the distinction between perceived and total latency.
- Apply at least two latency interventions, measuring each in isolation and checking quality side-effects rather than assuming them away.
- Report measured deltas against the budget, model versions, dependencies, token and dollar spend, and the exact command that reproduces every metric and chart.
- Include tests, generated metrics/charts, a ≤2-page final write-up, and an AI-collaboration log. Do not commit secrets, credentials, `.env` files, virtual environments, dependency caches, `node_modules`, or build folders.

## Repo-local skills

Repo-local skills are available without copying their contents into an active prompt or file. Before starting work, select the smallest set that matches the task and read the corresponding `SKILL.md` directly. Do not ask the user to load these files manually.

The canonical index is `.codex/.agents/skills/SKILLS.md`; its paths are relative to the repository root. The skill files are:

| Skill | Use for |
| --- | --- |
| `eval-first-rag` | Orchestrate the end-to-end RAG build, evaluation, and latency-optimization loop |
| `evaluating-llm-systems` | Freeze quality, latency, cost, and promotion gates before changes |
| `building-rag-pipelines` | Design or review the retrieval → generation pipeline |
| `reducing-llm-latency` | Instrument clocks, waterfall stages, budgets, and latency interventions |
| `retrieval-and-reranking` | Improve retrieval quality or context assembly |
| `selecting-models` | Compare or route models under quality, cost, and latency constraints |
| `diagnosing-llm-failures` | Investigate wrong outputs, regressions, or incidents |
| `build-llm-regression-gates` | Build reproducible candidate-vs-baseline regression gates |
| `build-representative-eval-datasets` | Create or expand representative evaluation datasets |
| `chose-graders-and-metrics` | Choose graders, metrics, and evaluation dimensions |
| `design-agent-guardrails` | Design or audit tool-use guardrails and approval boundaries |
| `build-bounded-agent-loops` | Design bounded, observable agent loops |
| `rlm-based-rag` | Evaluate adaptive RLM retrieval for large or context-rot-prone corpora |
| `review-plan` | Audit a plan for coverage, ordering, safety, and verification |

For code navigation, impact analysis, debugging, refactoring, and GitNexus operations, use the matching GitNexus skill when it is available in the agent environment. Read only the relevant skill; the registry is the persistent discovery mechanism.

For this project, begin with `eval-first-rag` for end-to-end work, and pair it with `reducing-llm-latency` and `evaluating-llm-systems`. Add focused skills only when the task requires them.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **latency-budget-teardown** (2379 symbols, 2314 relationships, 0 execution flows). Invoke GitNexus **on demand**, never as an automatic hook: automatic invocation adds friction and context/tool overhead. The targeted rules below provide the required protection.

Use the GitNexus MCP only for an unfamiliar-code query, an impact or refactoring analysis, debugging/tracing, security-taint inspection, or the required pre-commit change check. Prefer its CLI for indexing and repository maintenance. Do not enable it for routine documentation-only edits that do not touch a symbol.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/latency-budget-teardown/context` | Codebase overview, check index freshness |
| `gitnexus://repo/latency-budget-teardown/clusters` | All functional areas |
| `gitnexus://repo/latency-budget-teardown/processes` | All execution flows |
| `gitnexus://repo/latency-budget-teardown/process/{name}` | Step-by-step execution trace |

<!-- gitnexus:end -->
