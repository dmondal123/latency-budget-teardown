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

The current implementation also provides two offline foundation commands:

```bash
.venv/bin/python scripts/probe_feasibility.py
.venv/bin/python scripts/ingest_pdfs.py --corpus documents --output artifacts/evidence_manifest.v1.json
```

The first writes explicit host/configuration probe results and does not claim a model smoke test. The second reads PDFs in stable filename/page order and writes content-addressed page evidence records.

With Metal visible (`Device(gpu, 0)`), run the bounded runtime smoke test:

```bash
/Users/dmondal/.venv-vllm-metal/bin/python scripts/run_runtime_smoke.py --output artifacts/runtime_smoke.v1.json
```

It starts and stops only its own server, checks readiness, sends text and image requests, and preserves failure logs in the JSON artifact.

### M05 target-device feasibility evidence

On the Metal-accessible M4 Pro, run the full bounded feasibility suite with the pinned runtime:

```bash
/Users/dmondal/.venv-vllm-metal/bin/python scripts/run_m05_feasibility.py --output-dir artifacts/m05.v1
```

The runner starts and stops only servers it launches. It writes one JSON record per memory-fraction, cache, and concurrency condition plus `summary.json`; failures are retained and cause a nonzero exit. It tests memory fractions `0.60`, `0.70`, and `0.80`, records process RSS, `vm_stat`, and swap snapshots, requires GPU/Metal-worker evidence, compares cache-enabled and cache-disabled output, verifies black/red image identity, and runs warm concurrency 2 and 4 probes.

The default 4 GiB safety margin means a condition fails when observed server RSS exceeds 20 GiB on the 24 GiB target. This is a protective qualification threshold, not a memory reservation. Run the sweep while the laptop is otherwise quiet; it stops failed conditions but may make other applications sluggish if memory pressure rises.

## Data and repository hygiene

Source PDFs, downloaded model weights, virtual environments, caches, build outputs, credentials, and `.env` files are excluded from version control. Generated benchmark artifacts will be added only when required by the submission and when their provenance and size are verified.
