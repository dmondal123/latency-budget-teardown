# Project Context

## Assignment

Instrument an end-to-end retrieval → model → validation pipeline, produce stable p50/p95 latency waterfalls with tail analysis, set a defensible stage budget, and measure at least two isolated interventions with quality checks. The repository must reproduce all metrics/charts, pin versions, report spend, document AI collaboration, and ship a real ZIP with a final write-up of at most two pages.

`PROBLEM_STATEMENT.md` is authoritative. `RAG_PIPELINE_PLAN.md` is the approved implementation interpretation and cannot weaken the assignment.

## Approved scope

- Timebox: ten hours.
- Hardware: M4 Pro, 16 GB unified memory.
- Corpus/QA source: `rag-datasets/rag-mini-wikipedia` at revision `1f9f3b53fbc5995b85aab8e993504ad42c5f16f6`.
- Retrieval: deterministic BM25 over the text-corpus passages.
- Model: Ollama `qwen3:4b-instruct`, exact digest captured before measurement.
- Model mode: thinking disabled, temperature zero, local-only serving.
- Evaluation: 30 manually verified mappings, split 24 development / six holdout.
- Primary interventions: streaming and output-token reduction.
- Runtime cost: external API cost per completed task must remain `$0.00`.

The Hugging Face QA IDs are not assumed to be passage IDs. Gold passage mappings must be derived and manually verified. Existing PDF fixtures belong to the retired scope and are not valid evidence for this design.

## Non-negotiable measurement rules

- Freeze contracts, cases, budgets, dataset/index identity, and model/runtime identity before candidate measurements.
- Persist complete raw traces before aggregation.
- Use real percentile-ranked traces for additive waterfalls; never add marginal stage p95s and call the sum p95 TTC.
- Bootstrap by independent case, not repeated rows.
- Keep intervention deltas isolated and interleave conditions.
- Reject latency wins that violate fatal, aggregate-quality, or slice gates.
- Treat Ollama as opaque; report dispatch-to-first-token, not invented prefill data.
- Keep first-token displayed separate from TTFT and TTC.
- Open the six holdouts once, after selecting the accepted configuration.

## Latency decision policy

Provisional p95 targets are TTFE ≤300 ms, TTFT ≤3.9 s, and TTC ≤15 s. Reduce optional decode/output length first under pressure. Context reduction is a later, separately quality-gated option. Never remove citation validation, provenance, fatal gates, or required evidence.

## Current state

The plan and surrounding contracts have been migrated to text RAG. Pipeline code, migrated 30-case fixtures, benchmark traces, and generated reports remain pending. No planned threshold or budget is measured evidence.

## Repository discipline

Do not commit credentials, `.env`, virtual environments, model blobs, dataset or dependency caches, `node_modules`, or build folders. Include generated artifacts only when required and after provenance, attribution, and size checks.
