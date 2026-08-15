# Project Progress

This file is the current project status. Update it after each meaningful milestone, approval gate, experiment decision, or newly discovered blocker. Detailed benchmark evidence belongs in `EXPERIMENT_LOG.md`; significant human and agent decisions belong in `COLLABORATION_NOTES.md`.

## Current status

| Field | Value |
|---|---|
| Overall state | Foundation tooling implemented; runtime feasibility gate blocked |
| Current phase | D1 contract, fixtures, and vLLM-Metal feasibility |
| Approved plan | `RAG_PIPELINE_PLAN.md`, approved 2026-08-16 |
| Latest milestone | Deterministic PDF ingestion and offline feasibility probes implemented |
| Authoritative measurements | None yet |
| Active blocker | None for target-device smoke; model download/startup may still fail and must be recorded |
| Next gate | Run the real vLLM-Metal smoke, image identity, memory, swap, and prefix-cache gates |

## Milestones

| ID | Milestone | Status | Evidence | Updated |
|---|---|---|---|---|
| M01 | Refine and approve the RAG latency plan | Complete | `RAG_PIPELINE_PLAN.md` | 2026-08-16 |
| M02 | Create project tracking scaffolding | Complete | `PROGRESS.md`, `EXPERIMENT_LOG.md`, `COLLABORATION_NOTES.md` | 2026-08-16 |
| M03 | Freeze behavioral contract and quality gates | Complete | User approved M03; `contracts/behavioral_contract.v1.json` and `contracts/thresholds.2026-08-16.json` | 2026-08-16 |
| M04 | Verify eval cases and seal holdout | In progress | `eval/v1/`, `scripts/verify_eval.py`, and passing verifier; awaiting G1 approval | 2026-08-16 |
| M05 | Pass vLLM-Metal feasibility gate | In progress | `runtime_smoke.v4.json` passes text/image/health; remaining memory, swap, CPU-fallback, cache, and repeatability checks are planned | 2026-08-16 |
| M06 | Run instrumented baseline | Not started | Expected raw JSONL and baseline report | 2026-08-16 |
| M07 | Run isolated interventions | Not started | Expected experiment records for I1 through I5 | 2026-08-16 |
| M08 | Run accepted combined condition and holdout | Not started | Expected combined-run report | 2026-08-16 |
| M09 | Reproduce final metrics and package submission | Not started | Expected clean reproduction log and ZIP audit | 2026-08-16 |

Allowed status values are `Not started`, `In progress`, `Blocked`, `Complete`, and `Rejected`.

## Approval gates

| Gate | Reviewer must inspect | Acceptance condition | Status |
|---|---|---|---|
| G1 measurement contract | Behavioral contract, eval cases, model/runtime identity, numeric budgets | Explicit human approval before baseline execution | Pending |
| G2 baseline integrity | Raw trace completeness, p50/p95 waterfall arithmetic, marginal-percentile labels, tail slices | Explicit human approval before interpreting interventions | Pending |
| G3 intervention decisions | Isolated configuration deltas, confidence intervals, quality effects, failure evidence | Explicit accept or reject decision for each condition | Pending |
| G4 final delivery | Requirement coverage, raw-to-report traceability, reproduction log, artifact contents | Explicit final approval | Pending |

## Next actions

| Priority | Action | Completion evidence |
|---|---|---|
| P0 | Review and approve the versioned behavioral contract and dated thresholds | Explicit G1 approval and contract hash |
| P0 | Review and approve the 30-case dataset and sealed holdouts | Explicit G1 approval and saved verifier output |
| P0 | Pin Qwen3-VL and the vLLM-Metal environment | Environment manifest with exact revisions |
| P0 | Complete M05 runtime feasibility checks | Smoke, memory-fraction/OOM, swap, CPU-fallback, prefix-cache, and repeatability evidence |
| P0 | Build the deterministic PDF evidence manifest from the corpus | `scripts/ingest_pdfs.py` output and ingestion tests |
| P1 | Implement stage spans and the raw JSONL schema | Passing instrumentation tests |
| P1 | Run B0 baseline with at least 150 valid requests | Baseline raw data and report |

## Risks and decisions needing attention

| Risk or decision | Current treatment | Trigger for update |
|---|---|---|
| Qwen3-VL support is experimental on vLLM-Metal | Hard feasibility gate before authoritative measurement | Smoke failure, incorrect image identity, CPU fallback, OOM, or sustained swap |
| Target has 24 GB unified memory | Preflight memory-fraction sweep and worst-case two-image probe; v4 peaked at 17.08 GB | Memory pressure or swap changes the tail |
| Thirty eval cases are below the preferred 48 to 60 | Record as a quality-coverage limitation; do not treat latency repetitions as independent quality cases | Coverage gap or unstable slice result |
| Prefix caching may behave differently on the experimental multimodal path | Correctness-gated fixed policy; separate from application caches | Same-text/different-image or concurrent parity failure |
| p95 may be unstable at 150 samples | Bootstrap by case and extend in 30-request blocks up to 300 | Relative p95 TTC confidence-interval width exceeds 20% |

## Artifact index

| Artifact | Purpose | State |
|---|---|---|
| `PROBLEM_STATEMENT.md` | Authoritative assignment requirements | Present |
| `RAG_PIPELINE_PLAN.md` | Approved measurement and implementation plan | Present |
| `PROGRESS.md` | Current milestone, gate, risk, and next-action status | Present |
| `EXPERIMENT_LOG.md` | Append-only experiment protocol and evidence record | Present |
| `COLLABORATION_NOTES.md` | Human and AI direction, decisions, and corrections | Present |

## Progress update template

Copy this block for each meaningful update.

```markdown
### YYYY-MM-DD: Short milestone name

Status: In progress | Blocked | Complete | Rejected

What changed:

Evidence:

Decision or blocker:

Next action:
```

## History

### 2026-08-16: Measurement plan approved

Status: Complete

What changed: `RAG_PIPELINE_PLAN.md` was restructured around the stage contract, baseline protocol, p50/p95 waterfall method, quality gates, isolated interventions, latency budget, and a vLLM-Metal optimization lane.

Evidence: Human approval in the collaboration session and the approved plan file.

Decision: Use the structure-first plan as the implementation authority.

Next action: Freeze the behavioral contract, eval set, runtime identity, and numeric budgets.

### 2026-08-16: Tracking scaffolding created

Status: Complete

What changed: Added the progress tracker, append-only experiment record, and collaboration decision/correction log.

Evidence: `PROGRESS.md`, `EXPERIMENT_LOG.md`, and `COLLABORATION_NOTES.md` passed focused structure and content checks.

Decision: Use these files continuously throughout implementation and before each commit.

Next action: Begin the D1 contract, eval-fixture, and vLLM-Metal feasibility work.

### 2026-08-16: Ingestion and feasibility tooling implemented

Status: In progress

What changed: Added deterministic PyMuPDF page ingestion with document/page hashes and stable evidence IDs, plus offline host/configuration feasibility probes. Added focused tests and documented the commands in `README.md`.

Evidence: `scripts/ingest_pdfs.py`, `scripts/probe_feasibility.py`, `tests/test_ingest_and_feasibility.py`; full test suite passes with 5 tests.

Decision or blocker: Marked the implementation work complete, but kept M05 in progress. The sandbox denied `sysctl` memory telemetry, and the real model smoke, image identity, OOM, CPU-fallback, and sustained-swap checks remain outstanding.

Next action: Run the probes and pinned vLLM-Metal smoke checks in the target environment, then record the feasibility result before baseline execution.

### 2026-08-16: M03 approval and M05 feasibility attempt

Status: Blocked

What changed: M03 was explicitly approved. The pinned environment manifest and offline feasibility probe were run for M05.

Evidence: `scripts/verify_environment.py` passed. `scripts/probe_feasibility.py` passed text, swap-command, prefix-hash, and runtime-configuration checks, but reported missing memory telemetry. `vllm`, `mlx`, and `mlx_vlm` are not installed; `runtime.server_revision` remains unset.

Decision or blocker: Keep M05 blocked. The runtime is now installed and pinned, but `vllm --version` fails with `No Metal device available`, which is expected for this sandbox. Real multimodal smoke, image identity, OOM, CPU-fallback, sustained-swap, and multimodal prefix-cache checks require a Metal-accessible target.

Next action: Run M05 on the user’s Metal-accessible M4 Pro environment using the installed runtime, then record the smoke and memory evidence.

### 2026-08-16: Runtime smoke passed

Status: In progress

What changed: `artifacts/runtime_smoke.v4.json` passed server health, text generation, and image generation on the Metal-backed runtime. Peak observed memory was 17.08 GB on a machine with 24 GB available.

Evidence: Qwen3-VL returned `READY` for text and `black` for the image probe; the vLLM Metal worker shut down cleanly.

Decision or blocker: Treat the basic runtime smoke as passed, but do not close M05 yet. The 1×1 image produced a non-fatal channel-dimension warning, and the safety/cache checks remain open.

Remaining M05 plan:

1. Capture baseline memory and swap before startup, during model load, during text/image requests, and after shutdown using `vm_stat` and `sysctl`.
2. Sweep `VLLM_METAL_MEMORY_FRACTION` conservatively (for example `0.70`, `0.80`, `0.90`) with one fresh server per setting; record startup, success/failure, peak memory, and swap. Stop on OOM or sustained swap.
3. Verify no CPU fallback by recording `mx.default_device()`, runtime environment variables, and server logs; fail if the selected device is CPU or Metal worker initialization is absent.
4. Test prefix-cache parity with the same text prefix and changed image, changed text and same image, and cache-disabled control. Compare outputs and record cache-hit telemetry if exposed.
5. Repeat text and image requests in a fresh server and a warm server, then run concurrency 2 and 4 smoke requests. Record failures, latency, memory, and swap separately.

Next action: Run this checklist on the Metal-accessible machine and attach the resulting JSON evidence before approving M05.
