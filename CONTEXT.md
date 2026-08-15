# Project Context

## Assignment

This repository is a planning and tooling scaffold for a five-day latency-budget teardown of a local multimodal RAG system. The required outcome is an instrumented retrieval → model → validation pipeline with reproducible p50 and p95 waterfalls, a defensible per-stage latency budget, at least two isolated latency interventions, measured quality effects, and one-command reproduction.

The problem statement is authoritative: [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md). The implementation plan elaborates it but cannot override it: [RAG_PIPELINE_PLAN.md](RAG_PIPELINE_PLAN.md).

## Current state

The measurement plan is approved. No pipeline code, benchmark fixtures, raw benchmark data, generated metrics, or charts exist yet. All numeric allocations and model/runtime settings in the plan are candidates or provisional design targets until their stated approval and feasibility gates pass; they are not performance claims.

The current work begins with the D1 contract, evaluation fixtures, and vLLM-Metal feasibility gate. Project status, gates, and risks are maintained in [PROGRESS.md](PROGRESS.md).

## Target environment and scope

- Hardware target: M4 Pro with 16 GB unified memory.
- Serving candidate: `mlx-community/Qwen3-VL-4B-Instruct-4bit` through a pinned `vllm-metal` environment.
- Corpus: PDFs in `documents/`, represented as complete page/slide evidence units.
- Baseline retrieval: deterministic BM25; dense retrieval is excluded from baseline behavior.
- Serving: local only; external runtime API cost per completed task must remain `$0.00`.
- Scope: a single-user, warm-server headline benchmark plus separately reported cold-start, cache, and concurrency profiles.

vLLM-Metal multimodal support is experimental for the candidate. Text/image correctness, image identity, output parity, memory headroom, absence of sustained swap, and absence of silent CPU fallback are hard prerequisites for authoritative Metal measurements.

## Non-negotiable measurement rules

- Freeze the behavioral contract, quality gates, eval cases, runtime identity, and numeric budgets before comparing candidates.
- Persist full request traces and environment identity before reporting aggregates.
- Use aligned request traces for additive waterfalls; never add independent stage p95 values and call the result p95 TTC.
- Bootstrap latency uncertainty by case, not by repeated request rows.
- Evaluate every latency intervention independently and reject it if fatal gates or quality tolerances fail.
- Preserve deterministic citation and provenance validation on the critical path; reduce optional narration before reducing validation.
- Keep cache-hit and cache-miss measurements distinct. Streaming is a perceived-latency intervention, not evidence of a TTC improvement.
- Open sealed holdouts only once for the accepted combined condition.

## Latency decision policy

The intended user experience targets are first real feedback within 300 ms, first token within 3.9 s, and validated completion within 15 s at p95. Under pressure, reduce optional decode narration and output-token allowance first. Then consider image resolution or admitted-page count, each behind its own quality gate. Do not cut citation validation, fatal gates, provenance, or required evidence.

## Evidence vocabulary

| Label | Meaning |
| --- | --- |
| Frozen | Approved before candidate measurement and unchanged within a comparison. |
| Measured | Derived from raw traces produced by this repository. |
| Candidate | Proposed configuration that must pass a stated test. |
| Excluded | Out of the five-day critical path, with a recorded reason. |

## Working documents

| Document | Role |
| --- | --- |
| [README.md](README.md) | Purpose, current state, and reproduction contract. |
| [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) | Authoritative requirements and rubric. |
| [RAG_PIPELINE_PLAN.md](RAG_PIPELINE_PLAN.md) | Approved execution, evaluation, and optimization plan. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Component boundaries, data flow, observability, and operational model. |
| [PROGRESS.md](PROGRESS.md) | Current milestones, approval gates, risks, and next actions. |
| [TASKS.md](TASKS.md) | Checklist of pending work only. |
| [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) | Pre-registered experiment protocol and measured evidence once execution begins. |
| [COLLABORATION_NOTES.md](COLLABORATION_NOTES.md) | Significant human/AI decisions, corrections, and learnings. |
| [AGENTS.md](AGENTS.md) | Repository operating and validation rules. |

## Repository discipline

Do not commit credentials, `.env` files, model weights, virtual environments, dependency caches, `node_modules`, generated build folders, or source PDFs without confirming redistribution permission. Keep changes small, deterministic, reviewable, and backed by a focused external check. Generated benchmark artifacts are included only when submission requirements and provenance/size checks permit them.
