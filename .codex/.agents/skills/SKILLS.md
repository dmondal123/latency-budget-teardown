# Skills Index

This repository contains repo-local skill definitions under `.codex/.agents/skills/`.

The agent can discover and use these skills from this index; their contents do not need to be copied into an active prompt or file. To use a skill, open its `SKILL.md` file directly from the repository root.

## Available skills

| Skill | Purpose | Path |
| --- | --- | --- |
| `build-bounded-agent-loops` | Design bounded, observable agent loops | `.codex/.agents/skills/build-bounded-agent-loops/SKILL.md` |
| `build-llm-regression-gates` | Build reproducible candidate-vs-baseline regression gates | `.codex/.agents/skills/build-llm-regression-gates/SKILL.md` |
| `build-representative-eval-datasets` | Build representative evaluation datasets | `.codex/.agents/skills/build-representative-eval-datasets/SKILL.md` |
| `building-rag-pipelines` | Build or review a full RAG pipeline end to end | `.codex/.agents/skills/building-rag-pipelines/SKILL.md` |
| `chose-graders-and-metrics` | Choose graders and evaluation metrics | `.codex/.agents/skills/chose-graders-and-metrics/SKILL.md` |
| `design-agent-guardrails` | Design and audit agent guardrails | `.codex/.agents/skills/design-agent-guardrails/SKILL.md` |
| `diagnosing-llm-failures` | Root-cause wrong outputs, regressions, and incidents | `.codex/.agents/skills/diagnosing-llm-failures/SKILL.md` |
| `eval-first-rag` | Orchestrate an eval-first RAG build and optimization loop | `.codex/.agents/skills/eval-first-rag/SKILL.md` |
| `evaluating-llm-systems` | Design and gate LLM/RAG evals before shipping | `.codex/.agents/skills/evaluating-llm-systems/SKILL.md` |
| `reducing-llm-latency` | Reduce latency or token cost without weakening validation | `.codex/.agents/skills/reducing-llm-latency/SKILL.md` |
| `retrieval-and-reranking` | Improve retrieval quality and assemble prompt context | `.codex/.agents/skills/retrieval-and-reranking/SKILL.md` |
| `review-plan` | Review a proposed plan for correctness and coverage | `.codex/.agents/skills/review-plan/SKILL.md` |
| `rlm-based-rag` | Use RLM-style adaptive retrieval for large or rot-prone corpora | `.codex/.agents/skills/rlm-based-rag/SKILL.md` |
| `selecting-models` | Choose or route between models using hard constraints | `.codex/.agents/skills/selecting-models/SKILL.md` |

## GitNexus skills

These complementary repository skills live under `.claude/skills/gitnexus/`:

| Skill | Purpose | Path |
| --- | --- | --- |
| `gitnexus-cli` | Analyze, index, inspect status, clean, or generate a wiki | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |
| `gitnexus-debugging` | Trace bugs, errors, and unexpected behavior | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| `gitnexus-exploring` | Understand architecture and execution flows | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| `gitnexus-guide` | Reference GitNexus tools, resources, and schema | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| `gitnexus-impact-analysis` | Assess blast radius before code changes | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| `gitnexus-refactoring` | Safely rename, extract, split, move, or restructure code | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |

## Reference files

Several skills include reference docs under `references/`. These are load-bearing details, not separate skills.

- `.codex/.agents/skills/building-rag-pipelines/references/`
- `.codex/.agents/skills/diagnosing-llm-failures/references/`
- `.codex/.agents/skills/evaluating-llm-systems/references/`
- `.codex/.agents/skills/reducing-llm-latency/references/`
- `.codex/.agents/skills/retrieval-and-reranking/references/`
- `.codex/.agents/skills/rlm-based-rag/references/`
- `.codex/.agents/skills/selecting-models/references/`

## Suggested entry points

- Start with `eval-first-rag` for an end-to-end RAG system.
- Start with `evaluating-llm-systems` for any shipping decision.
- Start with `diagnosing-llm-failures` for incident triage.
- Start with `review-plan` when validating a proposed implementation plan.
