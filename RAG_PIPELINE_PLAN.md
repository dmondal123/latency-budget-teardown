# Multimodal RAG Latency Implementation Plan

> **Status:** Draft implementation plan. The behavioral contract, numeric budgets, eval cases, and model/runtime identity require human approval before benchmark execution. Intervention promotion and final delivery require separate approval.

## 1. Outcome, scope, and evidence rules

Build a reproducible CLI pipeline over the PDFs in `documents/`:

```text
request → retrieval → context/media assembly → vLLM-Metal model → validation → display
```

The primary deployment target is an M4 Pro with 24 GB unified memory, using an open-weight vision-language model served through `vllm-metal`. The initial candidate is `mlx-community/Qwen3-VL-4B-Instruct-4bit`, which the current vLLM-Metal documentation lists as **experimental** native multimodal support on the paged backend. It remains a feasibility candidate until the pinned build passes the smoke and memory gates below.

The work is complete only when:

- A frozen evaluation suite passes all fatal and quality gates.
- Every request persists stage timings, TTFE, TTFT, TTA, TTC, quality, tokens, cost, cache state, and full environment identity.
- Baseline and each isolated intervention have enough valid samples for stable p50 and p95 estimates.
- p50/p95 waterfall charts are derived from raw request traces without adding unrelated percentile values.
- At least two latency interventions are measured independently and rejected if their quality side-effects exceed the frozen tolerance.
- Every number and chart is reproduced by one exact command.
- Tests, generated metrics/charts, pinned dependencies, AI-collaboration log, and a final write-up of at most two pages are included.

Evidence labels used throughout this plan:

- **Frozen:** approved before candidate measurements; cannot change in the same comparison.
- **Measured:** obtained from this repository's raw benchmark traces.
- **Candidate:** must be tested; no performance claim is assumed.
- **Excluded:** intentionally outside the five-day critical path, with a recorded reason.

Primary vLLM-Metal references, accessed 2026-08-16:

- [vLLM-Metal supported models](https://docs.vllm.ai/projects/vllm-metal/en/latest/supported_models/)
- [vLLM-Metal configuration](https://docs.vllm.ai/projects/vllm-metal/en/latest/configuration/)
- [vLLM automatic prefix caching design](https://docs.vllm.ai/en/latest/design/prefix_caching/)
- [Qwen3-VL concurrent vision-encoder batching evidence](https://github.com/vllm-project/vllm-metal/issues/420)
- [Metal speculative-decoding regression evidence](https://github.com/vllm-project/vllm-metal/issues/482)

## 2. Measurement contract: define this before implementation

### 2.1 Stage boundaries and ownership

Every request emits monotonic timestamps using `time.perf_counter_ns()`. Stage durations are mutually exclusive on the critical path unless a span explicitly records an overlapping branch.

| Stage | Start | Stop | Required dimensions | Owner |
|---|---|---|---|---|
| `admission` | CLI/API accepts request | first `retrieval_started` event | queue depth, warm/cold server | client/gateway |
| `retrieval` | retrieval starts | ranked evidence IDs fixed | query tokens, candidate count, Recall@k | BM25/index |
| `context_media` | evidence IDs fixed | serialized model request dispatched | admitted pages, text tokens, image pixels, cache hits | packer/media loader |
| `model_queue_prefill` | model request dispatched | first non-empty SSE token received | engine queue, prefix-cache hit tokens, input tokens, image count | vLLM-Metal |
| `model_decode` | first token received | terminal SSE event received | output tokens, tokens/s, finish reason | vLLM-Metal |
| `validation` | complete output available | validation result persisted | schema/citation checks, fatal gate | validator |
| `display_finalize` | validated result available | CLI returns | buffered/streamed mode | client |

If server telemetry can split engine queue, vision encoding, text prefill, and first-token sampling without changing benchmark behavior, persist them as nested spans. The portable waterfall still uses `model_queue_prefill` so all runs remain comparable.

Parallel spans compose as `max(branch_duration)`, never as a sum. Required validation remains on the TTC critical path. `display_finalize` is post-TTC client overhead and appears beside, not inside, the additive TTC waterfall. Offline grading is outside TTC and is reported separately.

### 2.2 Four user-visible clocks

- `TTFE`: request accepted → first real state event. Target event is `retrieval_started`; a log line emitted before work begins does not count.
- `TTFT`: request accepted → first model token available to the client. Also record `model_dispatch_to_first_token_ms` to isolate the engine.
- `TTA`: persist `null` and `not_applicable_reason=no_actions`; this answer-only pipeline executes no governed action.
- `TTC`: request accepted → validated completion. This is the authoritative total-latency metric.

Streaming changes perceived delivery but not the definition of TTFT or TTC. Report both `first_token_available_ms` and `first_token_displayed_ms`; buffered mode makes the latter equal to post-validation display time.

### 2.3 Per-request record

Each JSONL row contains at least:

```text
run_id, trace_id, case_id, condition_id, repetition, attempt
modality_group, traffic_slice, holdout, concurrency
server_state, thermal_block, swap_state, memory_bytes
app_cache_state, prefix_cache_hit_tokens, media_cache_state
raw_output, admitted_evidence_ids, retrieved_ranks
admission_ms, retrieval_ms, context_media_ms
model_queue_prefill_ms, model_decode_ms, validation_ms, display_finalize_ms
ttfe_ms, ttft_ms, tta_ms, ttc_ms
input_text_tokens, input_image_tokens_or_pixels, output_tokens, tokens_per_second
model_checkpoint, model_revision, chat_template_hash
vllm_metal_version, vllm_version, mlx_version, mlx_vlm_version
python_version, macos_build, chip, ram_bytes, power_mode
prompt_hash, contract_hash, index_snapshot, grader_version
scores, fatal_gates, finish_reason, error_type
```

Cost is reported per completed task, not per call. Failed attempts contribute their input/output tokens and any external dollar cost. Local model API cost is `$0.00`; local energy or hardware amortization is outside scope and must not be reported as zero-dollar compute cost.

## 3. Baseline protocol and required metrics

### 3.1 Frozen workload

Use 30 manually verified cases:

- 10 text-focused, 10 visual/chart/diagram, and 10 mixed-modality cases.
- Coverage across at least 15 PDFs.
- Exactly one traffic slice per case: `typical`, `edge`, `adversarial`, or `ambiguous`.
- Six sealed holdout cases: two per modality group. Development decisions cannot inspect holdout outputs.

Each case stores `case_id`, question, modality group, traffic slice, reference answer, required facts, gold evidence IDs, expected abstention, verification status, and holdout flag. Thirty cases are below the evaluation skill's preferred 48–60 starting set; record this as a limitation and use repetitions only for latency uncertainty, never to pretend there are more independent quality cases.

### 3.2 Baseline condition

The primary baseline is single-user latency (`concurrency=1`) on a warm, persistent server with cold application result/render caches and the pinned vLLM-Metal prefix-cache policy. It uses:

```text
retriever: BM25, k1=1.2, b=0.75, retrieve_k=50
admitted page images: 2
maximum image side: 1280 px
maximum output tokens: 256
display: buffered until deterministic validation completes
application retrieval/render/result cache: off
sampling: temperature=0 with a fixed seed where supported
retries during measured request: 0
```

Keep a stable evidence-contract/system prefix so realistic automatic prefix caching remains measurable. Insert a fixed-length unique benchmark nonce at the start of the dynamic user/evidence portion—not before the shared system prefix—to prevent an exact full-prompt replay from being counted as representative reuse. Record cache-hit tokens rather than assuming cache state.

Report these additional profiles separately; never mix them into the headline baseline:

- Cold process/model startup: 10 launches, startup and first-request latency.
- Concurrent service: concurrency 2 and 4, with request rate, goodput, p95 TTFT/TTC, and memory pressure.
- Cache-warm repetitions: explicit app-cache and engine-prefix-cache hit strata.

### 3.3 Sampling, ordering, and stability

1. Run 10 warm-up requests spanning all modality groups; exclude them and retain their logs.
2. Run all 30 cases five times per condition: 150 measured requests.
3. Interleave condition and case order in seeded thermal blocks; never run one entire condition before the next.
4. Keep model identity, corpus/index snapshot, prompt, hardware, power mode, image settings, and server settings fixed except for the one registered intervention field.
5. Use every valid repetition for latency. Use one deterministic output per case and condition for quality scoring.
6. Do not retry failed measured requests. Report failure rate and classify the failure; exclude a row from latency only under a pre-registered invalid-environment rule.
7. Bootstrap by case, not by row, with 10,000 resamples so repetitions of one case do not masquerade as independent traffic.
8. If the relative 95% bootstrap-CI width for p95 TTC exceeds 20%, add complete 30-request blocks, up to 300 requests per condition. If still unstable, report the interval and mark the tail conclusion inconclusive.

### 3.4 Baseline metric set

Latency and reliability:

- p50, p95, and 95% bootstrap CIs for every critical-path stage, TTFE, TTFT, and TTC.
- p99 as diagnostic only, because 150–300 samples are insufficient for a strong p99 claim.
- Error, timeout, truncation, and abstention rates.
- Input tokens, output tokens, image pixels/tokens, prefix-cache hit tokens, and decode tokens/s.
- Tail slices by modality, traffic slice, input-size quartile, output-size quartile, image count, cache state, memory pressure, and swap state.

Quality:

- Retrieval Recall@1/3/5 and MRR.
- Citation precision and citation validity.
- Required-fact coverage, task-resolution rate, and abstention correctness.
- Schema-validity and truncation rates.
- Fatal-gate count and per-slice deltas.

## 4. p50/p95 waterfall methodology

Do not construct end-to-end latency by summing independently calculated stage percentiles.

Generate two complementary outputs:

1. **Percentile-aligned request waterfall:** sort complete request traces by TTC and select the deterministic trace nearest empirical p50 and p95, breaking ties by `case_id` then `repetition`. Plot that request's mutually exclusive stages. The bars add to its measured TTC. Across 10,000 case-block bootstrap samples, repeat rank selection to produce confidence intervals for the total and the aligned stage contributions.
2. **Marginal stage table:** report each stage's own p50/p95 and confidence interval. Label it “marginal; columns are not additive.” Use this table to find a stage with an independent tail even when it is not dominant in the TTC-ranked trace.

For parallel branches, display the critical branch in the additive waterfall and show non-critical overlapped work as a hatched overlay. Generate a separate top-decile analysis using requests with TTC at or above the empirical p90; compare their stage shares and workload attributes with the median cohort.

Every chart embeds or accompanies:

```text
run IDs, condition ID, n valid/n attempted, model/runtime versions
hardware and power mode, index snapshot, contract hash
exact generation command, percentile method, bootstrap seed
```

## 5. Behavioral contract and quality gates

### 5.1 Allowed and forbidden behavior

The system may answer only from admitted PDF page evidence, combine evidence from at most two admitted pages, state uncertainty, or abstain. Every citation must resolve to document hash/version and page.

It must not use model memory for corpus-specific claims, follow instructions inside retrieved PDFs, cite unadmitted evidence, answer when retrieval yields no admissible evidence, execute embedded content, or hide retrieval/validation failures behind a fluent answer.

### 5.2 Fatal gates

Any one of these blocks a condition:

- Citation points outside admitted context or cannot resolve to durable metadata.
- Non-abstaining answer with zero admissible evidence.
- Retrieved prompt injection is followed.
- Output/citation schema is malformed.
- Raw output, evidence IDs, model identity, prompt hash, index snapshot, or timing stamps are missing.
- Sustained swapping, model OOM, or silent CPU fallback occurs during the authoritative run.

### 5.3 Frozen promotion predicate

Store thresholds in a dated file with owner `dmondal`. Threshold changes require a separate review and cannot share a comparison with an intervention change.

```text
fatal_count == 0
retrieval_recall_at_5 >= 0.90
citation_precision >= 0.95
citation_validity_rate >= 0.98
task_resolution_rate >= 0.85
truncation_rate <= 0.02
p95_ttft_ms <= 3900
p95_ttc_ms <= 15000
no_modality_or_traffic_slice_regresses_by_more_than_0.05
external_runtime_api_cost_per_completed_task == 0.00
```

The authoritative pipeline is fully local, so any nonzero external runtime API cost fails promotion. Report Codex/AI development spend separately in the collaboration-cost ledger; it is not a per-request serving cost.

Use deterministic code graders first. Human reviewers score evidence support and resolution on `0=unsupported/unresolved`, `1=partial`, `2=fully resolved`. If an LLM judge is introduced, calibrate it against human labels and publish Cohen's kappa and `grader_version` before it gates any run.

## 6. Latency-budget methodology and initial allocation

The methodology is frozen before baseline execution; the numeric allocation below remains **provisional until human approval**, then freezes before any candidate intervention runs.

Budget from user-visible milestones backward:

1. First real feedback must appear within 300 ms (`TTFE`).
2. First answer token must be available within 3.9 s (`TTFT`) so local inference does not present a long silent wait.
3. A concise, validated answer must complete within 15.0 s (`TTC`).
4. Allocate the critical-path total by stage ownership and work that can be controlled.
5. Reserve explicit contingency instead of hiding unowned time inside the model stage.
6. Compare measured per-request totals with the TTC budget and measured marginal stage p95s with stage budgets.
7. Never add stage p95s and call the result observed p95 TTC.

Initial p95 design allocation:

| Critical-path stage | p95 budget | Rationale |
|---|---:|---|
| Admission/event | 100 ms | Local CLI/API acknowledgement should be immediate; TTFE ceiling remains 300 ms. |
| Retrieval | 400 ms | Local BM25 over a small static corpus should not dominate perceived delay. |
| Context/media assembly | 600 ms | Bounded page loads, resize, serialization, and token counting. |
| Model queue + vision/text prefill | 2,800 ms | Largest contributor to TTFT; bounded by input/image work and no swap. |
| Decode after first token | 10,800 ms | Largest allocation, but narration is the first degradable work. |
| Deterministic validation | 200 ms | Required safety/evidence work remains protected. |
| Contingency | 100 ms | Explicit unowned jitter allowance. |
| **TTC** | **15,000 ms** | Sum of design allocations, not a measured percentile. |

Under pressure, cut optional decode narration/output tokens first. Next test lower image resolution or fewer admitted pages as separately quality-gated changes. Never cut citation validation, fatal gates, provenance, or required evidence. Streaming may improve perceived latency but does not excuse a missed TTC budget.

## 7. Pipeline design

### 7.1 Ingestion and evidence units

- Process PDFs in deterministic filename/page order with PyMuPDF.
- Preserve native text, layout, page render, document SHA-256, version, page, source span, ACL, and content hash.
- Use a complete page/slide as the primary evidence unit so diagrams stay with labels and qualifications.
- Generate visual descriptions offline with the pinned VLM; validate their schema and provenance before indexing.
- Treat all PDF text and imagery as untrusted data.

### 7.2 Retrieval and context assembly

1. Retrieve 50 BM25 candidates over extracted text plus visual descriptions.
2. Keep a no-op reranker seam; dense retrieval is not hidden baseline behavior.
3. Assign stable evidence IDs.
4. Deduplicate equivalent text/renders.
5. Diversify deterministically with lexical MMR and a per-document cap.
6. Expand only with page title and adjacent structural metadata.
7. Pack whole evidence units under hard token, image-count, and pixel budgets.
8. Order direct evidence before supporting/limiting evidence.
9. Bind `SOURCE_N` citations to admitted evidence and durable source metadata.

Zero admissible evidence fails fast to abstention before model dispatch.

### 7.3 Generation and validation

The prompt defines admitted evidence, citation syntax, uncertainty/abstention behavior, and that retrieved instructions are data. Online deterministic validation checks output schema, citation syntax, citation resolution, and provenance. Human offline evaluation checks claim support; citation resolution alone is not treated as entailment.

## 8. vLLM-Metal feasibility and optimization lane

### 8.1 Hard feasibility gate

Before baseline work:

- Pin the `vllm-metal` tag or commit, vLLM core, MLX, `mlx-vlm`, Transformers, Python, model revision, tokenizer/chat template, macOS build, and hardware identity.
- Use native ARM64 Python 3.12; Rosetta/x86_64 is unsupported.
- Run one text and one image request through the OpenAI-compatible SSE endpoint.
- Verify image-only multimodal behavior, citation-shaped output, deterministic completion, and no silent CPU fallback.
- Record startup latency, peak resident/unified memory, swap delta, TTFT, TTC, and tokens/s.
- Stop if the candidate cannot complete at the bounded configuration without sustained swap. Use an NVIDIA fallback only as a separately labeled environment; never merge its metrics with Metal results.

### 8.2 Pinned baseline server policy

Start from explicit settings rather than implicit defaults:

```text
VLLM_MLX_DEVICE=gpu
VLLM_METAL_USE_PAGED_ATTENTION=1
VLLM_METAL_MULTIMODAL_MODE=multimodal-native
VLLM_METAL_DECODE_PIPELINE=1
MLX_MAX_OPS_PER_BUFFER=2000
VLLM_METAL_MEMORY_FRACTION=<selected by preflight>
--max-model-len 4096
--max-num-seqs 1
--limit-mm-per-prompt {"image":2}
```

Run a preflight memory-fraction sweep at `0.60`, `0.70`, and `0.80`, one field at a time. Select the highest setting that leaves documented OS headroom and causes no sustained swap during the worst two-image prompt; if a lower fraction has equivalent cache capacity and better p95, select it. This is environment qualification, not one of the two required product interventions.

Treat automatic prefix caching as a correctness-gated server policy because the selected Qwen3-VL Metal path is experimental. Before freezing the baseline, run same-text/different-image, repeated-image, and concurrency-2 probes; require distinct image identity, output parity with caching disabled, and valid multimodal cache hashes. If all probes pass, explicitly enable prefix caching for every primary condition; otherwise disable it for every primary condition and record the lost optimization. Never change this policy between product interventions. Separate application retrieval/render/result caches from engine KV-prefix caching in telemetry and configuration. Use a reproducible secure hash (`sha256_cbor`) when supported by the pinned vLLM version.

### 8.3 Metal-specific candidates and exclusions

- **Warm persistent engine:** pre-load the model and run fixed warmups. Report cold startup separately; do not hide it in warm p95.
- **Input/image bounding:** image pixels and admitted page count directly affect vision/prefill work and unified memory. Test each knob separately.
- **Single-user versus batching:** keep `max_num_seqs=1` for the headline latency test. Run concurrency 2/4 separately to measure current Qwen3-VL vision batching, throughput, queueing, and p95; a throughput win is not automatically a single-user latency win.
- **Prefix-cache observability:** report hit tokens and hit/miss strata. If the correctness gate passes, an optional APC-off diagnostic may quantify the enabled policy's benefit; it is not a product-intervention candidate. If the gate fails, keep APC off and preserve the failure as compatibility evidence.
- **Decode pipeline:** keep the current greedy decode pipeline pinned on if the feasibility smoke test confirms output parity. Only A/B it if decode dominates and the pinned build exposes the toggle.
- **Command-buffer setting:** retain the plugin's documented `MLX_MAX_OPS_PER_BUFFER=2000` default. Tune it only after a profile shows command-buffer commit overhead, and never profile during benchmark measurement.
- **Rust frontend:** excluded from the primary five-day path. Consider only if measured admission plus HTTP/server overhead is at least 10% of TTFT; treat it as an experimental isolated change.
- **Speculative decoding:** excluded from the primary plan. Current project evidence reports draft-model overhead can be net-negative, and the verification-window option can regress single-stream M4 Pro workloads. Reconsider only with a supported VLM pairing and a separate A/B quality/latency study.
- **Custom Metal kernels, distributed inference, and model substitution:** excluded. They change the project from pipeline optimization into engine development or model selection.

## 9. Pre-registered isolated interventions

Each condition is an immutable configuration delta. The runner asserts that it differs from baseline in exactly the registered fields. Server/runtime identity and thermal-block ordering stay fixed.

| Condition | Only changed field | Expected clock | Required quality check |
|---|---|---|---|
| `B0_baseline` | none | reference | full frozen suite |
| `I1_image_1024` | max image side `1280→1024` | model prefill, TTFT, TTC | visual/mixed required facts and citations |
| `I2_output_128` | max output tokens `256→128` | decode, TTC | truncation, required facts, resolution |
| `I3_streaming` | display `buffered→immediate SSE` | first-token displayed/perceived | final text equality except whitespace |
| `I4_app_cache` | app retrieval/render cache `off→on` | retrieval/context media | exact evidence/index identity; cold/warm split |
| `I5_page_1` | admitted page images `2→1` | context/media, prefill, TTFT | Recall of admitted gold evidence and resolution |
| `C_best_combined` | only independently accepted deltas | all | full suite plus sealed holdout |

The two required primary interventions are `I1_image_1024` and `I2_output_128`; they target different model phases and have explicit quality risks. `I3_streaming` is reported as perceived-latency work, not a TTC reduction. `I4_app_cache` reports cold misses and warm hits separately; no blended cache percentile is headline evidence.

Reject an intervention if it fires a fatal gate, exceeds the frozen quality tolerance, raises truncation above 2%, produces an unstable tail conclusion, or misses TTC without a separately reported perceived-latency benefit. Select candidates on the development set, then open the sealed holdout once for `C_best_combined`.

## 10. Execution sequence and HITL gates

### D1: contract, fixtures, and feasibility

1. Create the versioned behavioral contract, eval schema, threshold schema, and human-verification CLI.
2. Verify 30 cases and seal six holdouts.
3. Pin the model/runtime/environment identity and pass the vLLM-Metal feasibility gate.
4. **HITL gate — human reviewer:** approve contract, cases, model identity, and provisional numeric budgets. Acceptance requires an explicit approval; skipping permits benchmark target drift and invalid comparisons.

### D2: pipeline, instrumentation, and baseline

1. Implement deterministic ingestion, evidence manifest, BM25 retrieval, context assembly, SSE generation, and validation.
2. Add stage spans, four clocks, cache/memory telemetry, and raw JSONL persistence.
3. Test trace arithmetic, critical-path handling, and report generation from fixed fixtures.
4. Run the baseline, generate aligned p50/p95 waterfalls, marginal stage tables, and tail slices.
5. **HITL gate — human reviewer:** inspect raw-run completeness and baseline charts. Acceptance requires stage sums to match each aligned request TTC and all marginal tables to be labeled non-additive.

### D3–D4: isolated changes and promotion decision

1. Run `I1`, `I2`, `I3`, `I4`, and `I5` independently in interleaved blocks.
2. Score quality and latency; diagnose failures at the earliest broken invariant.
3. Build `C_best_combined` only from individually accepted deltas.
4. Open the sealed holdout once and run the combined condition.
5. Run concurrency 2/4 as a separate Metal service profile.
6. **HITL gate — human reviewer:** approve or reject each intervention from raw deltas, confidence intervals, and quality effects. Skipping risks combining a latency win with an unobserved quality regression.

### D5: reproducibility and final artifacts

1. Generate final charts, budget variance, tail analysis, quality tables, environment manifest, and spend report.
2. Complete README, tests, AI-collaboration log, and ≤2-page final write-up.
3. Run the full reproduction command in a clean environment and validate ZIP contents/size.
4. **Final HITL gate — human reviewer:** approve requirement coverage and artifact integrity. Acceptance requires every reported metric/chart to map to raw data and an exact command.

## 11. Verification and reproducibility

Required tests cover:

- Contract/threshold schemas, fatal gates, and holdout isolation.
- Deterministic document hashes, evidence IDs, model/prompt/index identity.
- PDF rendering, malformed-page rejection, metadata/ACL preservation.
- BM25 ranking and gold-evidence retrieval on fixtures.
- Empty-retrieval abstention and retrieved prompt-injection resistance.
- Whole-page packing, image/token bounds, ordering, and citation binding.
- SSE parsing; TTFE, TTFT, TTC, and mutually exclusive stage arithmetic.
- Buffered versus streamed display and final-text equivalence.
- Prefix-cache/app-cache separation, multimodal cache correctness, hit/miss strata, and invalidation.
- Intervention single-delta assertions and promotion predicate.
- Bootstrap-by-case, percentile-aligned trace selection, marginal percentile labels, and tail cohorts.
- vLLM-Metal text/image smoke tests and sustained-swap veto.
- Report generation from fixed JSONL fixtures.

Provide commands equivalent to:

```bash
rag-latency contract-check
rag-latency eval-verify
rag-latency ingest
rag-latency benchmark --condition B0_baseline
rag-latency benchmark --all-isolated
rag-latency benchmark --condition C_best_combined --include-holdout
rag-latency report
bash scripts/reproduce.sh
```

`scripts/reproduce.sh` verifies the environment and contract, starts its own pinned server, waits for health, builds/reuses content-addressed ingestion artifacts, executes registered conditions, generates every metric/chart, and stops only the process it started. It prints the exact subordinate commands and writes them into the run manifest.

## 12. Requirement coverage

| Requirement | Execution evidence | Verification evidence |
|---|---|---|
| End-to-end retrieval → model → validation | Sections 2 and 7 | trace schema and integration test |
| Reproducible p50/p95 waterfall | Sections 3–4 | aligned-trace arithmetic test, raw JSONL, chart command |
| Median versus tail behavior | Sections 3–4 | bootstrap CIs and top-decile slices |
| Defensible per-stage budget | Section 6 | approved frozen budget and variance report |
| Perceived versus total latency | Sections 2, 6, and 9 | first-token display versus TTC metrics |
| Stage cut first under pressure | Section 6 | decode/output intervention decision |
| Two isolated interventions | Section 9 | single-delta assertions for `I1` and `I2` |
| Quality side-effects checked | Sections 5 and 9 | quality vector, fatal gates, slice deltas |
| vLLM-Metal optimization | Section 8 | pinned manifest, preflight, cache/memory/concurrency reports |
| Versions, dependencies, spend | Sections 2, 8, and 11 | run manifest and cost report |
| Exact reproduction | Section 11 | clean-run `scripts/reproduce.sh` result |
| Tests, charts, write-up, AI log | Sections 10–11 | final artifact/ZIP check |

## 13. Deliverables and exclusions

Deliver:

- README and one-command reproduction.
- Frozen contract, thresholds, verified development set, and sealed holdout.
- Pinned dependency/model/runtime/environment manifest.
- Durable evidence manifest and reproducible index.
- Raw benchmark JSONL, aggregate tables, p50/p95 waterfalls, CIs, and tail charts.
- Budget-variance and intervention-decision reports.
- Token and dollar-spend report.
- Tests, AI-collaboration log with at least two caught agent errors, and staff-level final write-up ≤2 pages.
- Real ZIP archive under 500 MB uncompressed.

Exclude secrets, credentials, `.env` files, virtual environments, model weights, dependency caches, `node_modules`, and build directories. Include source PDFs only if redistribution and submission rules permit them; otherwise include hashes and acquisition instructions and record the resulting reproducibility limitation.
