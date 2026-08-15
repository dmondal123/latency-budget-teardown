# Experiment Log

This is the append-only record of benchmark and feasibility experiments. Create an entry before running a command, then fill in results, observations, learnings, and the decision immediately after the run. Never replace measured values with estimates or copy values by hand from a chart.

## Logging rules

1. Use one stable experiment ID per registered condition and run attempt.
2. Record the hypothesis and the single intended configuration delta before execution.
3. Link the exact command, immutable configuration, raw data, generated report, and environment manifest.
4. Keep failed and invalid runs. Mark why they failed or why they were excluded.
5. Report latency and quality together. A latency improvement is not accepted without its quality checks.
6. Separate cold and warm state, cache hit and miss, single-user and concurrent profiles, and perceived and total latency.
7. Do not add stage percentiles to derive end-to-end p50 or p95.
8. Update `PROGRESS.md` when an experiment changes a milestone, gate, risk, or next action.

## Experiment index

| Experiment | Description | Intended delta | Status | Decision | Entry |
|---|---|---|---|---|---|
| F0 | vLLM-Metal feasibility and memory qualification | Environment qualification, not a product intervention | Planned | Pending | Add run entry below |
| B0 | Instrumented baseline | None | Planned | Reference condition | Add run entry below |
| I1 | Lower image-resolution bound | Maximum image side `1280→1024` | Planned | Pending | Add run entry below |
| I2 | Lower output-token bound | Maximum output tokens `256→128` | Planned | Pending | Add run entry below |
| I3 | Immediate SSE display | Display `buffered→immediate` | Planned | Pending | Add run entry below |
| I4 | Application cache | Retrieval/render cache `off→on` | Planned | Pending | Add run entry below |
| I5 | One admitted page image | Admitted page images `2→1` | Planned | Pending | Add run entry below |
| C1 | Best accepted combination | Only independently accepted deltas | Blocked by I1 through I5 | Pending | Add run entry below |

Allowed run status values are `Planned`, `Running`, `Complete`, `Invalid`, `Failed`, and `Blocked`.

Allowed decisions are `Reference`, `Accept`, `Reject`, `Rerun`, `Inconclusive`, and `Pending`.

## Experiment entry template

Copy this complete section for every run. Do not delete fields. Use `Not applicable` when a field genuinely does not apply and explain why.

```markdown
## EXP-YYYYMMDD-NNN: Short experiment name

### Description

Experiment ID:
Registered condition:
Owner:
Date and timezone:
Status:
Decision:

Question:

Hypothesis:

Single intended delta:

Expected affected clock or stage:

Expected quality risk:

### Frozen inputs and environment

Baseline run ID:
Contract hash:
Eval dataset version:
Holdout included: No
Corpus and index snapshot:
Model checkpoint and revision:
Chat-template hash:
vLLM-Metal, vLLM, MLX, mlx-vlm, Transformers, and Python versions:
macOS build, chip, RAM, and power mode:
Server configuration path or hash:
Application configuration path or hash:
Randomization seed:
Concurrency:
Warm or cold policy:
Application cache policy:
Prefix-cache policy:

### Steps

1. Confirm the contract, dataset, index, model, runtime, and configuration hashes.
2. Assert that the condition differs from baseline only by the registered delta.
3. Start or verify the pinned server and record health, memory, and swap state.
4. Run the pre-registered warmup without including it in measured samples.
5. Run the exact benchmark command and preserve stdout, stderr, exit status, and raw JSONL.
6. Generate latency, waterfall, tail, quality, token, cost, and failure reports from raw data.
7. Run the condition gate and record the decision without changing thresholds.

Exact command:

```bash
# Paste the exact reproducible command here before execution.
```

Raw data path:
Run manifest path:
Report command:
Generated report and chart paths:

### Results

Sample integrity:

| Metric | Baseline | Candidate | Absolute delta | Relative delta | 95% CI | Budget | Pass |
|---|---:|---:|---:|---:|---:|---:|---|
| Valid / attempted | | | | | | | |
| Failure rate | | | | | | | |
| TTFE p50 | | | | | | 300 ms | |
| TTFE p95 | | | | | | 300 ms | |
| TTFT p50 | | | | | | | |
| TTFT p95 | | | | | | 3,900 ms | |
| TTC p50 | | | | | | | |
| TTC p95 | | | | | | 15,000 ms | |
| Output tokens p50 | | | | | | | |
| Decode tokens/s p50 | | | | | | | |
| External runtime API cost/completed task | | | | | | $0.00 | |

Stage results:

| Stage | p50 | p95 | 95% CI | p95 budget | Delta from budget | Notes |
|---|---:|---:|---:|---:|---:|---|
| Admission/event | | | | 100 ms | | |
| Retrieval | | | | 400 ms | | |
| Context/media | | | | 600 ms | | |
| Model queue and prefill | | | | 2,800 ms | | |
| Decode after first token | | | | 10,800 ms | | |
| Validation | | | | 200 ms | | |

Quality and safety:

| Metric | Baseline | Candidate | Delta | Frozen gate | Pass |
|---|---:|---:|---:|---:|---|
| Fatal count | | | | 0 | |
| Retrieval Recall@5 | | | | ≥0.90 | |
| Citation precision | | | | ≥0.95 | |
| Citation validity | | | | ≥0.98 | |
| Task resolution | | | | ≥0.85 | |
| Truncation rate | | | | ≤0.02 | |
| Worst modality/traffic-slice regression | | | | ≤0.05 | |

Tail behavior:

Top-decile dominant stage:
Slowest modality or traffic slice:
Input/output/cache/memory correlation:
Swap or thermal evidence:
Relative p95 TTC CI width:
Additional samples required:

### Observations

State only what the traces, outputs, and environment logs show.

### Learnings

Explain what the result changes about the pipeline, budget, runtime configuration, or next experiment.

### Decision and follow-up

Gate result:
Decision rationale:
Unexpected failure classification:
Regression test added:
Follow-up experiment or task:
Progress file updated:
Collaboration note updated:
```

## Run entries

No experiment has been executed yet.
