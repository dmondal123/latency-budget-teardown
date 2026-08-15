# Latency Budget Teardown

This repository is the planning and tooling scaffold for a reproducible multimodal RAG latency study on Apple Silicon.

The target pipeline is:

```text
request → retrieval → context/media assembly → vLLM-Metal model → validation → display
```

The study will measure p50 and p95 stage waterfalls, separate perceived from total latency, freeze a per-stage budget, and evaluate latency interventions without assuming away quality regressions.

## Current state

The measurement and implementation plan is approved. Pipeline code, evaluation fixtures, benchmark data, and generated charts have not been created yet. Do not treat plan values as measured results.

## Core documents

| Document | Purpose |
|---|---|
| `PROBLEM_STATEMENT.md` | Authoritative assignment requirements |
| `RAG_PIPELINE_PLAN.md` | Approved pipeline, evaluation, latency, and vLLM-Metal plan |
| `PROGRESS.md` | Milestones, gates, risks, and next actions |
| `EXPERIMENT_LOG.md` | Pre-registered experiments and measured evidence |
| `COLLABORATION_NOTES.md` | Human and AI decisions, corrections, and learnings |
| `TASKS.md` | Workspace task sequence |
| `AGENTS.md` | Repository working and validation rules |

## Planned baseline

The baseline uses a deterministic BM25 retrieval path, bounded PDF page evidence, Qwen3-VL served through a pinned `vllm-metal` environment, deterministic citation validation, and raw per-request JSONL telemetry.

Headline evidence will include:

- p50 and p95 TTFE, TTFT, and TTC.
- Percentile-aligned request waterfalls plus non-additive marginal stage percentiles.
- Bootstrap confidence intervals and top-decile tail analysis.
- Retrieval, citation, resolution, abstention, schema, and truncation quality metrics.
- Token and dollar spend per completed task.
- Isolated image-resolution and output-token interventions, with streaming and caching reported separately.

## Reproduction contract

The final implementation must provide one command:

```bash
bash scripts/reproduce.sh
```

That command does not exist yet. When implemented, it must verify the environment, start its own pinned model server, run registered conditions, generate every reported metric and chart from raw data, and stop only the process it started.

## Data and repository hygiene

Source PDFs, downloaded model weights, virtual environments, caches, build outputs, credentials, and `.env` files are excluded from version control. Generated benchmark artifacts will be added only when required by the submission and when their provenance and size are verified.
