# Architecture

## Purpose

This project measures and improves the latency of a local multimodal RAG pipeline without relaxing evidence, citation, or validation requirements. The authoritative behavior and acceptance criteria remain in [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md); the approved execution details are in [RAG_PIPELINE_PLAN.md](RAG_PIPELINE_PLAN.md).

## System boundary

```text
PDF corpus
    │ deterministic ingestion
    ▼
Evidence manifest + BM25 index ───────────────────────────────────┐
    │                                                              │
    │ request                                                       │
    ▼                                                              │
Admission → Retrieval → Context/media assembly → vLLM-Metal → Validation → Display
    │              │                  │                 │              │
    └──────────────┴──────────────────┴─────────────────┴──────────────┘
                         per-request trace and run manifest
                                              │
                                              ▼
                         JSONL reports, waterfall charts, gates
```

The benchmarked path ends at validated completion. Offline quality grading and report generation consume saved outputs but are outside that request's time-to-validated-completion (TTC).

## Components and responsibilities

| Component | Responsibility | Durable output |
| --- | --- | --- |
| Ingestion | Read PDFs in deterministic filename/page order; extract page text, render pages, and preserve source metadata. | Content-addressed evidence manifest and index snapshot. |
| Retrieval | Run the pinned BM25 configuration over native text and validated visual descriptions; rank and return evidence IDs. | Ranked candidates and retrieval telemetry. |
| Context/media assembly | Deduplicate, diversify, bound, and serialize whole-page evidence under token, image-count, and pixel limits. | Admitted evidence IDs and model request. |
| Model service | Serve the pinned Qwen3-VL candidate through vLLM-Metal and emit SSE tokens. | Raw model output and engine telemetry. |
| Validation | Enforce output schema, citation syntax, citation resolution, provenance, and fatal gates. | Validated answer or failure classification. |
| Display | Present buffered or streaming output; record when the first token is displayed. | Client completion event. |
| Benchmark harness | Execute immutable conditions in seeded thermal blocks and persist one complete trace per attempt. | Raw JSONL, run manifest, environment identity. |
| Reporting and evaluation | Derive quality metrics, percentile-aligned waterfalls, marginal stage tables, CIs, and tail analysis solely from saved traces. | Tables, charts, and promotion decision. |

## Request lifecycle and timing contract

Every request uses monotonic timestamps. Critical-path spans are mutually exclusive unless a trace explicitly records overlap; parallel branches contribute their maximum duration rather than their sum.

| Span | Boundary | Primary owner | Budgeted p95 |
| --- | --- | --- | ---: |
| `admission` | Request accepted → retrieval begins | Client/gateway | 100 ms |
| `retrieval` | Retrieval begins → evidence IDs fixed | BM25/index | 400 ms |
| `context_media` | Evidence IDs fixed → model request dispatched | Packer/media loader | 600 ms |
| `model_queue_prefill` | Dispatch → first non-empty SSE token | vLLM-Metal | 2,800 ms |
| `model_decode` | First token → terminal SSE event | vLLM-Metal | 10,800 ms |
| `validation` | Complete output → result persisted | Validator | 200 ms |
| contingency | Explicit unowned jitter reserve | System | 100 ms |

The resulting provisional p95 TTC design budget is 15,000 ms. `display_finalize` is recorded beside the waterfall as client overhead, not included inside additive TTC. The budget becomes frozen only after human approval before benchmark execution.

The four clocks are recorded independently:

- TTFE: request acceptance to the first real work event.
- TTFT: request acceptance to the first model token available to the client.
- TTA: always `null` for this answer-only system, with a reason recorded.
- TTC: request acceptance to validated completion; the authoritative total-latency clock.

Streaming can improve perceived latency (first token displayed) but cannot improve TTC by definition unless the underlying path is faster.

## Evidence, safety, and quality boundary

The model receives only admitted evidence. It can answer from that evidence, state uncertainty, or abstain; it cannot follow retrieved instructions or cite evidence outside the admitted context. A zero-evidence retrieval result fast-fails to abstention before model dispatch.

Deterministic online validation is always on the TTC path. It checks the output schema, citation form, citation resolution, and provenance. Citation resolution does not prove claim support, so human offline evaluation separately scores support and task resolution.

Fatal gates block a condition for malformed or unresolved citations, unsupported answers with no evidence, followed prompt injection, missing trace identity, swapping/OOM, or silent CPU fallback.

## Measurement and experiment architecture

The harness stores raw JSONL before aggregation. A record contains trace and run IDs, case and condition identity, spans and four clocks, retrieved/admitted evidence, cache and memory state, tokens, model/runtime/environment identity, output, scores, and errors.

The headline waterfall selects a request at the desired TTC percentile and plots that request's additive spans; this keeps the bars equal to a real measured TTC. Marginal stage percentile tables are reported separately and labeled non-additive. Bootstrap resampling is by case, not by repetition, and top-decile TTC traces form the tail cohort.

Each intervention is a single immutable delta from the baseline. The two required primary interventions are image-size reduction and maximum-output-token reduction. Streaming and application caching are measured separately because they affect perceived latency or cache strata differently. A combined condition contains only independently accepted deltas and opens the sealed holdout once.

## Reproducibility and operations

The planned `scripts/reproduce.sh` command will verify the pinned environment, start only its own model server, run registered conditions, generate all reported artifacts from raw data, and stop only the process it started. It will record every subordinate command in the run manifest.

The authoritative environment is native ARM64 Python 3.12 on an M4 Pro with 16 GB unified memory. Before baseline measurement, the candidate vLLM-Metal build must pass text and image smoke tests, multimodal cache-correctness probes, and memory/swap gates. An NVIDIA fallback, if necessary, is a separately labeled environment and cannot be combined with Metal measurements.
