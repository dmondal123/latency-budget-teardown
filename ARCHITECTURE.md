# Architecture

## Purpose

This project measures and improves a local text-RAG pipeline while preserving retrieval evidence, citations, deterministic validation, and reproducibility.

`PROBLEM_STATEMENT.md` is authoritative; `RAG_PIPELINE_PLAN.md` defines the approved ten-hour execution scope.

## System boundary

```text
Pinned Hugging Face corpus
    │ deterministic normalization
    ▼
Passage manifest + BM25 index
    │
    ▼
Admission → Retrieval → Context assembly → Ollama → Validation → Display
    │                                                               │
    └──────────────────── raw request trace and run manifest ───────┘
                                      │
                                      ▼
                         quality tables, waterfalls, gates
```

The benchmarked path ends at validated completion. Offline grading and reporting consume saved traces and remain outside request TTC.

## Components

| Component | Responsibility | Durable output |
| --- | --- | --- |
| Dataset preparation | Load the pinned corpus/QA configs, verify schemas, select 30 QA rows, and manually verify QA-to-passage mappings. | Dataset manifest and 24/6 eval split |
| Ingestion | Normalize passages in ID order and hash corpus content. | Evidence manifest and index snapshot |
| Retrieval | Run frozen BM25 and return ranked passage IDs. | Ranked IDs, scores, gold rank |
| Context assembly | Admit five bounded passages and bind `SOURCE_N` citations. | Model prompt and admitted IDs |
| Model client | Call pinned Ollama `qwen3:4b` with thinking disabled and parse NDJSON streaming. | Raw output and observable token metadata |
| Validation | Enforce output schema, citations, provenance, and fatal gates. | Validated answer or classified failure |
| Benchmark harness | Run immutable conditions in seeded thermal blocks. | Raw JSONL and run manifest |
| Evaluation/reporting | Compute quality, aligned waterfalls, marginal stages, CIs, tails, and decisions from traces. | Tables, charts, gate report |

## Timing contract

All client timestamps are monotonic. Ollama is an opaque boundary; client timing must not be mislabeled as internal queue or prefill telemetry.

| Span | Boundary | Provisional p95 budget |
| --- | --- | ---: |
| `admission` | Request accepted → retrieval begins | 100 ms |
| `retrieval` | Retrieval begins → ranked IDs fixed | 200 ms |
| `context_assembly` | Ranked IDs fixed → request dispatched | 300 ms |
| `model_dispatch_to_first_token` | Dispatch → first non-empty answer token | 3,000 ms |
| `model_decode` | First token → terminal response | 11,200 ms |
| `validation` | Full output → validation persisted | 100 ms |
| contingency | Explicit jitter reserve | 100 ms |

The provisional p95 TTC budget is 15,000 ms. `display_finalize` is shown beside, not within, the additive TTC waterfall. TTFE, TTFT, first-token displayed, TTA, and TTC are stored independently.

## Evidence and quality boundary

The model can use only admitted passages, cite their stable IDs, state uncertainty, or abstain. It cannot use model memory for corpus-specific claims, follow retrieved instructions, cite unadmitted evidence, or hide retrieval/validation errors.

Online validation checks schema, citation syntax, citation resolution, and provenance. Offline evaluation measures Recall@k, MRR, normalized exact match, token F1, task resolution, citation quality, truncation, and slice regressions.

## Experiment architecture

The 24 development cases run five times under each condition:

- `B0_buffered_256`
- `I1_streaming_256`
- `I2_buffered_128`

Conditions are interleaved and differ in exactly one registered field. Six sealed holdouts run only after the accepted configuration is selected. The headline waterfalls plot real p50/p95-ranked TTC traces; marginal stage percentiles are reported separately and labeled non-additive. Bootstrap resampling is by case.

## Operations

The authoritative environment is native ARM64 macOS on an M4 Pro with 16 GB unified memory. Before measurement, capture the Ollama version, immutable `qwen3:4b` digest, thinking-disabled request mode, dataset revision, file hashes, index snapshot, and host identity. `scripts/reproduce.sh` must stop only processes it started and must never package model blobs or caches.
