# Latency Budget Teardown

This repository contains the documentation and tooling foundation for a reproducible local **text-RAG latency study** on Apple Silicon.

The approved pipeline is:

```text
question → BM25 retrieval → bounded text context → Ollama/qwen3:4b-instruct → validation → display
```

The study will produce p50 and p95 latency waterfalls, distinguish perceived from total latency, freeze a per-stage budget, and measure two latency interventions without assuming away quality regressions.

## Current state

Wave 1 preflight and the Wave 2 evaluation/retrieval foundations are complete. The project has:

- a pinned `rag-datasets/rag-mini-wikipedia` dataset revision and materialization evidence;
- a deterministic BM25 retrieval and bounded-context foundation with focused tests;
- 30 manually verified text-QA cases, split into 24 development and six sealed holdout cases;
- a validated local Ollama `qwen3:4b-instruct` runtime with thinking disabled, immutable digest, and version recorded;
- G1-approved behavioral and threshold contracts; and
- only Ollama runtime tooling and evidence, after the retired alternative runtime path was removed.

No authoritative benchmark measurements, charts, or intervention decisions exist yet. The current blocker is implementation of T12, T13, and T14 before the C03 integration gate.

## Frozen scope

- **Dataset:** `rag-datasets/rag-mini-wikipedia` at revision `1f9f3b53fbc5995b85aab8e993504ad42c5f16f6`
- **Retriever:** deterministic BM25 with bounded top-five context assembly
- **Model service:** local Ollama `qwen3:4b-instruct`, temperature `0`, `think=false`
- **Primary interventions:** streaming display and reducing the output-token cap from 256 to 128

PDF ingestion, multimodal models, dense retrieval, reranking, and concurrency optimization are out of scope for this study.

## Reproducibility status

Dependencies are pinned in `requirements.txt`, generated from `requirements.in`. The validated preflight artifacts are:

- `artifacts/lock.v1.json`
- `artifacts/dataset_materialization.v1.json`
- `artifacts/ollama_preflight.v1.json`

The following foundation commands are available from the repository root:

```bash
.venv/bin/python scripts/verify_environment.py
.venv/bin/python scripts/verify_eval.py
.venv/bin/python -m scripts.retrieval.run --help
```

Run one full, local, citation-validated query (its ad-hoc trace files are kept out of version control):

```bash
.venv/bin/python -m scripts.pipeline \
  --manifest artifacts/text_evidence_manifest.v1.json \
  --question "Did Lincoln sign the National Banking Act of 1863?" \
  --stream
```

The environment check validates the captured Ollama `0.32.13` identity and the
immutable `qwen3:4b-instruct` digest recorded in
`environment/manifest.v1.json`.

The final reproducibility command will be:

```bash
bash scripts/reproduce.sh
```

It is intentionally not implemented until the pipeline instrumentation, benchmark runner, and report generation work are complete. When available, it will regenerate all reported metrics and charts from saved raw traces.

## Planned evidence

The final study will report:

- p50/p95 TTFE, TTFT, first-token-displayed time, and TTC;
- percentile-aligned waterfalls, non-additive marginal stage tables, bootstrap intervals, and tail analysis;
- retrieval, citation, resolution, exact-match/token-F1, truncation, and error metrics;
- input/output tokens and cost per completed task; and
- isolated baseline-versus-intervention deltas against the frozen quality and latency gates.

## Core documents

| Document | Purpose |
| --- | --- |
| `PROBLEM_STATEMENT.md` | Authoritative assignment requirements |
| `RAG_PIPELINE_PLAN.md` | Approved text-RAG pipeline, evaluation, latency, and model plan |
| `PROGRESS.md` | Milestones, approval gates, risks, and next actions |
| `TASKS.md` | Current execution sequence and checklist |
| `contracts/behavioral_contract.v1.json` | Draft executable behavioral contract for G1 review |
| `contracts/thresholds.2026-08-16.json` | Draft quality and latency thresholds for G1 review |
| `EXPERIMENT_LOG.md` | Pre-registered experiments and measured evidence once benchmarking starts |
| `COLLABORATION_NOTES.md` | Significant human/AI decisions, corrections, and learnings |
| `AGENTS.md` | Repository operating and validation rules |

## Data and repository hygiene

Do not commit model weights, downloaded datasets, virtual environments, dependency caches, build outputs, credentials, `.env` files, or other secrets. Generated measurement artifacts are committed only when required for the submission and when their provenance and size have been verified.
