# Project Progress

Use this file for current milestone, approval, risk, and blocker state. Detailed measurements belong in `EXPERIMENT_LOG.md`; significant human/AI decisions and corrections belong in `COLLABORATION_NOTES.md`.

## Current status

| Field | Value |
| --- | --- |
| Overall state | Wave 5 holdout complete (T20 done); Wave 6 reproduction and delivery remain |
| Current phase | Wave 6 reproduction and packaging |
| Approved plan | `RAG_PIPELINE_PLAN.md`, revised 2026-08-16 |
| Latest milestone | T20 holdout completed: 90 attempts, 0 fatal gates, 0 errors, C07 accepted |
| Authoritative measurements | `artifacts/authoritative-runs/20260816T112509Z-1df7268307b1/` (development C05) and `artifacts/authoritative-runs/20260816T172257Z-612d93faccd1/` (holdout C07) |
| Active blocker | C07 requires T21 final-report generation before package delivery |
| Next gate | C07 traceability of holdout reports |

## Milestones

| ID | Milestone | Status | Evidence |
| --- | --- | --- | --- |
| M01 | Approve revised ten-hour text-RAG plan | Complete | `RAG_PIPELINE_PLAN.md` |
| M02 | Pin dataset repository/revision and observed schemas | Complete | `eval/v1/dataset_manifest.json`; both configurations materialized with downloaded-file and normalized-corpus hashes |
| M03 | Migrate behavioral contract and thresholds | Complete | G1-approved JSON contracts and frozen provisional thresholds |
| M04 | Build and verify 30 text QA cases | Complete | `eval/v1/candidate_ledger.json`, `eval/v1/reviewed_mappings.json`, sealed 24/6 fixtures, and authoritative verifier pass |
| M05 | Pin and smoke-test Ollama `qwen3:4b-instruct` | Complete | `artifacts/ollama_preflight.v1.json`; Ollama `0.32.13`, immutable digest captured, buffered/streaming parity passes, zero sustained swap |
| M06 | Implement instrumented text-RAG pipeline | Complete | T12–T15.2 stage spans, telemetry, raw traces, condition/report fixtures, representative tail diagnostics, and local manual-query CLI |
| M07 | Run baseline and two isolated interventions | Complete | T16 raw traces, validations, warmups, and C05-accepted manifest |
| M08 | Generate waterfalls, tails, quality, and decisions | Complete | T17/T18/T19 reports and scripts |
| M09 | Run accepted holdout and reproduce/package | In progress | T20 holdout run complete; T21–T25 packaging remain |

## Approval gates

| Gate | Reviewer must inspect | Acceptance condition | Status |
| --- | --- | --- | --- |
| G1 measurement contract | Dataset/evidence mappings, contract, thresholds, Ollama/model identity | Explicit approval before baseline | Approved 2026-08-16 |
| G2 baseline integrity | Trace completeness, stage arithmetic, aligned waterfalls, marginal labels | Explicit approval before intervention decisions | Pending |
| G3 intervention decisions | Single deltas, intervals, quality/truncation effects | Explicit accept/reject per condition | Pending |
| G4 final delivery | Raw-to-report traceability, reproduction log, archive contents | Explicit final approval | Pending |

## Immediate actions

| Priority | Action | Completion evidence |
| --- | --- | --- |
| P0 | Run authoritative baseline and isolated interventions serially | T16 raw JSONL and run manifest |
| P1 | Preserve the external dataset cache and rerun the materializer before fixture verification when needed | `scripts.ingestion.materialize` and `scripts/verify_eval.py` |

## Risks

| Risk | Treatment | Trigger |
| --- | --- | --- |
| QA IDs may be mistaken for passage IDs | Never infer the mapping; verify answer-containing passages manually | Any selected row lacks unique support |
| `qwen3:4b-instruct` tag is mutable | Capture immutable Ollama digest before measurement | Digest missing or changes |
| Qwen thinking tokens distort latency | Require `think=false` and reject traces showing reasoning mode | Smoke/output metadata mismatch |
| p95 is unstable with 120 rows/condition | Case bootstrap; extend in 24-row blocks only if time permits | Relative p95 CI width >20% |
| Warm server or OS state drifts | Interleaved seeded blocks, fixed keep-alive/power mode, record swap | Thermal/swap changes |
| Ten-hour deadline encourages weak evidence | Drop optional diagnostics before reducing validation or fabricating gold mappings | Schedule slips |

## History

### 2026-08-16: Text-RAG scope approved

Status: Complete

What changed: Replaced PDF and multimodal ingestion with the pinned `rag-mini-wikipedia` text dataset, Ollama `qwen3:4b-instruct`, and two primary interventions: streaming and output-token reduction.

Evidence: Human approval and `RAG_PIPELINE_PLAN.md`.

Important correction: Dataset inspection confirmed gold answers but found no documented QA-ID-to-passage-ID relationship. The revised plan requires manual gold evidence verification rather than treating IDs as interchangeable.

Follow-through: The immutable model/runtime identity, 30-case suite, and G1 approval are complete. The next work is Wave 3 instrumentation and integration.

### 2026-08-16: Runtime cleanup completed

Status: Complete

What changed: Removed the retired alternative runtime scripts and generated evidence. The project now has one local runtime path: Ollama `qwen3:4b-instruct`.

Evidence: `artifacts/ollama_preflight.v1.json`, `environment/manifest.v1.json`, and `.venv/bin/python scripts/verify_environment.py`.

Decision: Ollama was selected because the available time did not support completing and validating the alternative runtime path.

### 2026-08-16: Original measurement scaffolding

Status: Superseded

The original multimodal plan and tracking scaffold established useful timing, waterfall, bootstrap, quality-gate, and reproducibility methods. Those methods are retained; the PDF-specific implementation direction is retired.
