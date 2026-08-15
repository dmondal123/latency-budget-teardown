# Project Progress

This file is the current project status. Update it after each meaningful milestone, approval gate, experiment decision, or newly discovered blocker. Detailed benchmark evidence belongs in `EXPERIMENT_LOG.md`; significant human and agent decisions belong in `COLLABORATION_NOTES.md`.

## Current status

| Field | Value |
|---|---|
| Overall state | Planning and documentation scaffolding |
| Current phase | D1 contract, fixtures, and vLLM-Metal feasibility |
| Approved plan | `RAG_PIPELINE_PLAN.md`, approved 2026-08-16 |
| Latest milestone | Measurement-first RAG pipeline plan approved |
| Authoritative measurements | None yet |
| Active blocker | None recorded |
| Next gate | Approve the behavioral contract, eval cases, pinned runtime identity, and numeric budgets before baseline execution |

## Milestones

| ID | Milestone | Status | Evidence | Updated |
|---|---|---|---|---|
| M01 | Refine and approve the RAG latency plan | Complete | `RAG_PIPELINE_PLAN.md` | 2026-08-16 |
| M02 | Create project tracking scaffolding | Complete | `PROGRESS.md`, `EXPERIMENT_LOG.md`, `COLLABORATION_NOTES.md` | 2026-08-16 |
| M03 | Freeze behavioral contract and quality gates | In progress | `contracts/behavioral_contract.v1.json`, `contracts/thresholds.2026-08-16.json`; awaiting G1 approval | 2026-08-16 |
| M04 | Verify eval cases and seal holdout | In progress | `eval/v1/`, `scripts/verify_eval.py`, and passing verifier; awaiting G1 approval | 2026-08-16 |
| M05 | Pass vLLM-Metal feasibility gate | Not started | Expected environment manifest and smoke-test record | 2026-08-16 |
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
| P0 | Run text, image, memory, swap, and prefix-cache correctness probes | Feasibility experiment record |
| P1 | Implement stage spans and the raw JSONL schema | Passing instrumentation tests |
| P1 | Run B0 baseline with at least 150 valid requests | Baseline raw data and report |

## Risks and decisions needing attention

| Risk or decision | Current treatment | Trigger for update |
|---|---|---|
| Qwen3-VL support is experimental on vLLM-Metal | Hard feasibility gate before authoritative measurement | Smoke failure, incorrect image identity, CPU fallback, OOM, or sustained swap |
| M4 Pro has 16 GB unified memory | Preflight memory-fraction sweep and worst-case two-image probe | Memory pressure or swap changes the tail |
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
