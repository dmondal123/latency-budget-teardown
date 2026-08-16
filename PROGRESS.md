# Project Progress

Use this file for current milestone, approval, risk, and blocker state. Detailed measurements belong in `EXPERIMENT_LOG.md`; significant human/AI decisions and corrections belong in `COLLABORATION_NOTES.md`.

## Current status

| Field | Value |
| --- | --- |
| Overall state | Wave 1 preflight is complete; C01 passed |
| Current phase | Wave 2 evidence and pipeline foundations |
| Approved plan | `RAG_PIPELINE_PLAN.md`, revised 2026-08-16 |
| Latest milestone | PDF/vLLM-Metal scope replaced by text Hugging Face/Ollama scope |
| Authoritative measurements | None |
| Active blocker | G1 approval of the verified 30-case suite, text-RAG contract, and provisional budgets is pending |
| Next gate | G1 approval of migrated cases, immutable runtime identity, and numeric budgets |

## Milestones

| ID | Milestone | Status | Evidence |
| --- | --- | --- | --- |
| M01 | Approve revised ten-hour text-RAG plan | Complete | `RAG_PIPELINE_PLAN.md` |
| M02 | Pin dataset repository/revision and observed schemas | Complete | `eval/v1/dataset_manifest.json`; both configurations materialized with downloaded-file and normalized-corpus hashes |
| M03 | Migrate behavioral contract and thresholds | In progress | Draft JSON contracts; awaiting G1 |
| M04 | Build and verify 30 text QA cases | Complete | `eval/v1/candidate_ledger.json`, `eval/v1/reviewed_mappings.json`, sealed 24/6 fixtures, and authoritative verifier pass |
| M05 | Pin and smoke-test Ollama `qwen3:4b-instruct` | Complete | `artifacts/ollama_preflight.v1.json`; Ollama `0.32.13`, immutable digest captured, buffered/streaming parity passes, zero sustained swap |
| M06 | Implement instrumented text-RAG pipeline | Not started | Expected source and passing tests |
| M07 | Run baseline and two isolated interventions | Not started | Expected raw JSONL and manifests |
| M08 | Generate waterfalls, tails, quality, and decisions | Not started | Expected scripted reports |
| M09 | Run accepted holdout and reproduce/package | Not started | Expected clean log and ZIP audit |

## Approval gates

| Gate | Reviewer must inspect | Acceptance condition | Status |
| --- | --- | --- | --- |
| G1 measurement contract | Dataset/evidence mappings, contract, thresholds, Ollama/model identity | Explicit approval before baseline | Pending |
| G2 baseline integrity | Trace completeness, stage arithmetic, aligned waterfalls, marginal labels | Explicit approval before intervention decisions | Pending |
| G3 intervention decisions | Single deltas, intervals, quality/truncation effects | Explicit accept/reject per condition | Pending |
| G4 final delivery | Raw-to-report traceability, reproduction log, archive contents | Explicit final approval | Pending |

## Immediate actions

| Priority | Action | Completion evidence |
| --- | --- | --- |
| P0 | Review the verified 30-case suite and provisional contract at G1 | Explicit G1 approval before baseline |
| P1 | Regenerate the application dependency lock | `requirements.in` / `requirements.txt` |
| P1 | Implement BM25 pipeline and request trace schema | Focused tests |
| P1 | Freeze budgets and quality thresholds at G1 | Explicit approval and contract hash |

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

What changed: Replaced PDF/multimodal ingestion and experimental vLLM-Metal with the pinned `rag-mini-wikipedia` text dataset, Ollama `qwen3:4b-instruct`, and two primary interventions: streaming and output-token reduction.

Evidence: Human approval and `RAG_PIPELINE_PLAN.md`.

Important correction: Dataset inspection confirmed gold answers but found no documented QA-ID-to-passage-ID relationship. The revised plan requires manual gold evidence verification rather than treating IDs as interchangeable.

Next action: Capture the immutable model/runtime identity and build the migrated 30-case suite for G1.

### 2026-08-16: Original measurement scaffolding

Status: Superseded

The original multimodal plan and tracking scaffold established useful timing, waterfall, bootstrap, quality-gate, and reproducibility methods. Those methods are retained; the PDF/vLLM-specific implementation direction is retired.
