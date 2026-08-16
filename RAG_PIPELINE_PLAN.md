# Text RAG Latency Implementation Plan

> **For agentic workers:** Execute the work in `TASKS.md` sequentially, using test-first changes and review checkpoints. Parallelize only disjoint implementation files; authoritative measurements remain serial on the target M4 Pro.

**Goal:** Build and measure a reproducible local text-RAG pipeline within ten hours while preserving rigorous latency and quality evaluation.

**Architecture:** A pinned Hugging Face text corpus feeds deterministic BM25 retrieval and bounded context assembly. A pinned Ollama qwen3:4b service generates cited answers; validation and raw tracing precede scripted quality and latency reports.

**Tech stack:** Python 3.12, Hugging Face Datasets, `rank-bm25`, HTTPX, Ollama, Qwen3 4B, JSONL, NumPy, Matplotlib, JSON Schema, and pytest/unittest.

> **Status:** Approved design, pending implementation and G1 measurement-contract approval. This revision is intentionally scoped for a ten-hour build-and-measurement window. Numeric budgets remain provisional until G1; no value in this document is a measured result.

## 1. Goal, scope, and completion contract

Build a reproducible local CLI pipeline:

```text
question → BM25 retrieval → context assembly → Ollama/qwen3:4b → validation → display
```

The corpus and gold questions come from the Hugging Face dataset `rag-datasets/rag-mini-wikipedia` at immutable revision `1f9f3b53fbc5995b85aab8e993504ad42c5f16f6`:

- `text-corpus`, split `passages`: `id`, `passage`
- `question-answer`, split `test`: `id`, `question`, `answer`

The dataset supplies gold answers but does **not** document a QA-ID-to-passage-ID mapping. The evaluation-preparation step must therefore find candidate passages by normalized answer containment and manually verify the final gold evidence ID for each selected case. The plan never treats the QA `id` as a passage ID.

Work is complete only when:

- The frozen 30-case suite has 24 development cases and six sealed holdouts.
- The development set is run five times for baseline and each isolated intervention.
- Every attempt persists raw output, evidence IDs, stage timings, TTFE, TTFT, TTA, TTC, tokens, scores, cache state, and full dataset/model/runtime identity.
- Reproducible p50/p95 waterfalls, marginal stage tables, bootstrap intervals, and top-decile tail analysis are generated only from saved traces.
- Streaming and output-token reduction are measured independently against the same baseline, latency budget, and frozen quality gates.
- One exact command regenerates every reported number and chart.
- Tests, generated metrics/charts, pinned dependencies, spend, collaboration log, final write-up of at most two pages, and a valid submission ZIP are present.

Out of scope: PDFs, image ingestion, multimodal models, dense retrieval, reranking, vLLM-Metal, concurrency optimization, speculative decoding, and production serving.

## 2. Frozen identities and fail-fast preflight

Freeze these before authoritative measurements:

- Dataset repository, revision, configurations, splits, downloaded-file hashes, license (`CC BY 3.0`), and derived index snapshot.
- Ollama version and the immutable digest returned for `qwen3:4b`.
- Model mode: thinking/reasoning disabled, temperature `0`, fixed seed where Ollama supports it, and a hashed prompt template.
- macOS build, architecture, chip, memory, Python version, dependency lock, power mode, and application commit or source snapshot.

Preflight must finish within 45 minutes:

1. Verify the pinned dataset revision and both expected schemas.

2. Pull or locate `qwen3:4b`, capture its digest, and confirm local-only serving.

3. Send one non-streaming and one streaming request with `think=false`.

4. Verify deterministic final-text parity, terminal streaming metadata, token counts, no OOM, and no sustained swap.

5. Stop rather than benchmark if the dataset schema differs, the model digest is unavailable, thinking cannot be disabled, or streaming is malformed.

The Ollama API is treated as an opaque service boundary. Do not claim separate engine queue and prefill times that the API cannot observe.

## 3. Measurement contract

### 3.1 Critical-path stages

Use `time.perf_counter_ns()` for all client-owned timestamps.

| Stage | Start | Stop | Required dimensions |
|---|---|---|---|
| `admission` | CLI accepts request | First `retrieval_started` event emitted | Warm/cold server |
| `retrieval` | Retrieval starts | Ranked passage IDs fixed | Query terms, candidate count, gold rank |
| `context_assembly` | Ranked IDs fixed | Ollama request dispatched | Admitted IDs, passages, input characters/tokens |
| `model_dispatch_to_first_token` | Request dispatched | First non-empty answer token received | Input/output tokens when available, stream mode |
| `model_decode` | First answer token received | Terminal response received | Output tokens, tokens/s, finish reason |
| `validation` | Full output available | Validation record persisted | Schema, citation, answer checks |
| `display_finalize` | Validated output available | CLI returns | Buffered/streamed mode |

The first six spans are mutually exclusive and add to TTC except that `display_finalize` is reported separately as client overhead. Offline grading and report generation are outside TTC.

### 3.2 User-visible clocks

- **TTFE:** Request accepted → real `retrieval_started` event.
- **TTFT:** Request accepted → first model answer token available to the client.
- **`first_token_displayed_ms`:** Request accepted → first token actually displayed; equal to post-validation display time in buffered mode.
- **TTA:** `null`, with `not_applicable_reason=no_actions`.
- **TTC:** Request accepted → deterministic validation completed.

Streaming is a perceived-latency intervention. It is not reported as a TTC win unless the measured TTC itself changes.

### 3.3 Raw trace schema

Each JSONL row includes at least:

```text
run_id, trace_id, case_id, source_row_id, condition_id, repetition, attempt,
answer_type, holdout, server_state, cache_state, raw_output,
retrieved_evidence_ids, admitted_evidence_ids, retrieved_ranks, admission_ms,
retrieval_ms, context_assembly_ms, model_dispatch_to_first_token_ms,
model_decode_ms, validation_ms, display_finalize_ms, ttfe_ms, ttft_ms,
first_token_displayed_ms, tta_ms, ttc_ms, input_tokens, output_tokens,
tokens_per_second, finish_reason, error_type, dataset_repo, dataset_revision,
corpus_hash, index_snapshot, model_tag, model_digest, think_mode,
ollama_version, prompt_hash, contract_hash, python_version, macos_build,
chip, ram_bytes, power_mode, scores, fatal_gates
```

If Ollama omits a token or timing field, persist `null` plus a reason. Never infer engine-internal timings from client observations.

## 4. Evaluation design

### 4.1 Frozen workload

Select 30 QA rows deterministically from the pinned `question-answer/test` split with seed `20260816`. Stratify across answer types:

- Boolean (`yes`/`no` variants)
- Numeric/date
- Named entity or short phrase
- Longer free-form answer

For each selected row, find all corpus passages containing the normalized gold answer, inspect the candidates, and record exactly one or more verified gold passage IDs. Reject a row if its evidence is absent, ambiguous, malformed, or requires outside knowledge; draw the next row in seeded order. Store the source row ID so selection is replayable.

Freeze 24 cases for development and six for holdout, stratified by answer type.

The holdout questions and evidence IDs may be materialized for reproducibility, but their outputs and aggregate quality are not inspected until the final accepted configuration is chosen.

Each case contains:

```text
case_id, source_row_id, question, reference_answer, answer_type,
gold_evidence_ids, support_quote, expected_abstention=false,
verification_status=manually_verified, holdout
```

Adversarial prompt-injection, empty-retrieval, and abstention behavior stay as deterministic unit/integration fixtures. They do not masquerade as dataset cases.

### 4.2 Quality metrics

- **Retrieval:** Recall@1/3/5 and MRR against verified gold passage IDs; gold-rank distribution and zero-gold-retrieval rate.
- **Generation and validation:** Citation precision and validity; normalized exact match and token F1; task-resolution rate using deterministic containment/boolean normalization, with documented manual review for ambiguous free-form cases; schema-validity, truncation, abstention, and error rates.
- Metrics are sliced by answer type and question/context/output-length quartiles.

Repetitions quantify latency uncertainty; they do not increase the number of independent quality cases. Use one deterministic output per case and condition for quality scoring.

### 4.3 Fatal gates and promotion predicate

Any of these blocks a condition:

A citation is outside admitted context or does not resolve to a pinned passage.

A non-abstaining answer has zero admissible evidence.

Retrieved instructions are followed as instructions.

Output/citation schema is malformed.

Raw output, evidence IDs, timing stamps, dataset/index identity, or model digest is missing.

Thinking mode is enabled, the model OOMs, or sustained swap occurs.

Freeze the dated thresholds before baseline execution:

```text
fatal_count == 0
retrieval_recall_at_5 >= 0.90
citation_precision >= 0.95
citation_validity_rate >= 0.98
task_resolution_rate >= 0.85
answer_token_f1 >= 0.80
truncation_rate <= 0.02
p95_ttft_ms = 3900
p95_ttc_ms <= 15000
no_answer_type_slice_regresses_by_more_than_0.05
external_runtime_api_cost_per_completed_task == 0.00
```

Threshold changes require separate approval and cannot share a comparison with an intervention change. Local Ollama API spend is `$0.00`; development-agent spend is reported separately and is not serving cost.

## 5. Baseline and sampling protocol

### 5.1 Baseline condition

`B0_buffered_256` uses:

```text
retriever: BM25, k1=1.2, b=0.75

retrieve_k: 20

admitted_top_k: 5

maximum output tokens: 256

display: buffered until deterministic validation completes

application result/retrieval cache: off

Ollama keep_alive: fixed for all conditions

think: false

temperature: 0

retries during measured request: 0
```

Passages are admitted in rank order under a hard character/token budget. Every passage is labeled `SOURCE_N` and mapped to its durable corpus passage ID.

### 5.2 Sampling and ordering

1. Run six excluded warmups spanning answer types.
2. Run 24 development cases five times per condition: 120 measured requests.
3. Interleave condition, case, and repetition order in seeded thermal blocks.
4. Keep every field fixed except the registered condition delta.
5. Do not retry measured failures; report them in the denominator.
6. Bootstrap by case with 10,000 resamples and seed `20260816`.
7. If relative p95 TTC CI width exceeds 20%, add complete 24-request blocks up to 240 requests per condition if the ten-hour deadline still permits it; otherwise report the interval and mark the tail conclusion inconclusive.

8. Run the six holdouts five times only for the accepted final configuration.

The primary matrix is 360 development requests plus 30 final holdout requests.

Benchmark requests are serial on the M4 Pro; parallel agents may implement and review code but may not parallelize authoritative measurements on the same host.

## 6. Waterfalls and tail analysis

Never sum independent stage percentiles and label the result p95 TTC.

Generate:

1. **Percentile-aligned request waterfalls:** Sort complete traces by TTC, select the deterministic trace nearest empirical p50 and p95, and plot that trace's mutually exclusive stages. Bars must add to its measured TTC.
2. **Marginal stage table:** Report each stage's p50/p95 and case-bootstrap interval, labeled “marginal; columns are not additive.”
3. **Tail report:** Compare traces at or above p90 TTC with the median cohort using stage shares, answer type, question length, context length, output length, gold rank, and error/truncation state.

Every artifact records run IDs, condition, valid/attempted counts, dataset/model identity, environment, contract/index hashes, bootstrap seed, percentile method, and exact generation command.

## 7. Provisional p95 latency budget

The methodology freezes before baseline; these values freeze only after G1.

| Critical-path stage | p95 budget | Rationale |
|---|---:|---|
| Admission/event | 100 ms | Local CLI acknowledgement should be immediate. |
| Retrieval | 200 ms | Small in-memory BM25 index. |
| Context assembly | 300 ms | Five bounded text passages; no media work. |
| Dispatch to first token | 3,000 ms | Observable Ollama request/prompt-processing boundary. |
| Decode after first token | 11,200 ms | Largest budget and first stage cut under pressure. |
| Deterministic validation | 100 ms | Required citation/schema checks remain protected. |
| Contingency | 100 ms | Explicit unowned jitter. |
| **TTC** | **15,000 ms** | Design allocation, not a measured percentile. |

TTFE remains capped at 300 ms and TTFT at 3.9 s. Under pressure, reduce optional decode length first. Next consider a separately quality-gated context reduction.

Never remove citation validation, provenance, fatal gates, or required evidence.

## 8. Pre-registered isolated interventions

| Condition | Only changed field | Expected effect | Required quality check |
|---|---|---|---|
| `B0_buffered_256` | None | Reference | Full development suite |
| `I1_streaming_256` | Display: buffered → streamed | Immediate first-token displayed/perceived latency | Normalized final-text and citation equality; token F1, task resolution, truncation |
| `I2_buffered_128` | Output tokens: 256 → 128 | Decode and TTC | Token F1, task resolution, truncation |

Each condition is an immutable delta. The runner rejects configurations that differ from baseline in any unregistered field.

Streaming is accepted when it materially improves first-token display without changing normalized final output or quality. Output reduction is accepted only if its latency interval improves and no fatal, aggregate, or slice gate fails. Do not combine changes merely because point estimates look favorable.

After decisions on the development set, define `C_accepted` from accepted deltas and open the six holdouts once. Exact-query caching and `admitted_top_k` 5→3 are optional follow-up diagnostics only if required work finishes early; they cannot replace either primary intervention or delay final delivery.

## 9. Ten-hour execution sequence

| Window | Work | Exit evidence |
|---|---|---|
| 0:00–0:45 | Dataset/Ollama preflight and immutable pins | Passing text/stream smoke, dataset schema, model digest |
| 0:45–2:00 | Materialize corpus, 30 verified cases, BM25 index | Corpus/index hashes, 24/6 split, verifier output |
| 2:00–4:30 | Pipeline, Ollama client, validation, trace writer | Focused unit and integration tests |
| 4:30–5:30 | Benchmark runner and fixed-fixture report tests | Condition-delta and waterfall arithmetic tests |
| 5:30–7:30 | Interleaved B0/I1/I2 measurements | Raw JSONL and complete run manifests |
| 7:30–8:30 | Quality scoring, CIs, waterfalls, tails, decisions | Generated tables/charts and gate report |
| 8:30–9:15 | Accepted holdout run and final report generation | Sealed holdout decision evidence |
| 9:15–10:00 | Clean reproduction, write-up, spend, ZIP audit | Reproduction log and valid archive |

Fail-fast rules:

If preflight exceeds 45 minutes, record the blocker before changing runtime or model; do not silently mix identities.

If the full 30-case gold mapping is not verified by two hours, use no fabricated mappings. Reduce implementation extras, not evidence integrity.

If benchmark time threatens delivery, stop optional extensions and report wide p95 intervals honestly.

Human approval is required at G1 before measurement, G2 after baseline integrity,

G3 for intervention decisions, and G4 before final packaging.

## 10. Verification and reproducibility

Required tests cover:

Dataset revision/schema and deterministic 30-case selection.

Verified QA-to-passage mappings, unique IDs, and 24/6 holdout isolation.

Deterministic corpus/index/prompt/model identity.

BM25 ranking and Recall@k/MRR fixtures.

Context bounds, ordering, and `SOURCE_N` citation binding.

Empty retrieval, abstention, and retrieved prompt-injection resistance.

Ollama NDJSON streaming, thinking-disabled requests, errors, and timeouts.

TTFE/TTFT/TTC boundaries and additive stage arithmetic.

Buffered/streamed final-text equivalence.

Normalized exact match, token F1, citation, and truncation graders.

Single-delta condition assertions and promotion predicate.

Bootstrap-by-case, aligned-trace selection, non-additive marginal labels, and top-decile cohorts.

Report generation from fixed JSONL fixtures.

Target commands:

```bash
rag-latency contract-check
rag-latency eval-prepare
rag-latency eval-verify
rag-latency ingest
rag-latency benchmark --conditions B0_buffered_256,I1_streaming_256,I2_buffered_128
rag-latency decide
rag-latency benchmark --condition C_accepted --include-holdout
rag-latency report
bash scripts/reproduce.sh
```

scripts/reproduce.sh verifies pins and contracts, starts or validates only its

own expected Ollama service/model identity, reuses content-addressed downloads and ingestion artifacts, runs registered conditions, regenerates artifacts, and stops only processes it started. It writes every subordinate command to the run manifest.

## 11. Requirement coverage

| Requirement | Execution | Verification |
|---|---|---|
| Retrieval model validation | Sections 3 and 5 | Integration trace and stage-arithmetic tests |
| Stable p50/p95 waterfalls | Sections 5–6 | Raw traces, case bootstrap, aligned-trace test |
| Tail separate from median | Section 6 | Top-decile cohort report |
| Defensible stage budget | Section 7 | Frozen G1 budget and variance report |
| Perceived versus total latency | Sections 3 and 8 | Displayed-first-token versus TTC |
| Stage cut first under pressure | Section 7 | Output-token intervention |
| Two isolated interventions | Section 8 | Single-delta assertions for I1/I2 |
| Quality effects | Sections 4 and 8 | Retrieval, citation, F1, resolution, slice gates |
| Versions/dependencies/spend | Sections 2 and 10 | Manifests and spend report |
| Exact reproduction | Section 10 | Clean `scripts/reproduce.sh` log |
| Tests/charts/write-up/AI log | Sections 9–10 | Artifact audit and ZIP check |

## 12. Deliverables and exclusions

Deliver source, tests, README, frozen contracts, dataset/eval/runtime manifests, derived evidence/index manifests, raw JSONL, generated tables/charts, decision and budget reports, spend, collaboration log, final write-up, reproduction log, and a real ZIP under 500 MB uncompressed.

Do not include credentials, `.env`, virtual environments, Ollama model blobs, Hugging Face caches, dependency caches, or build directories. Include downloaded dataset files only if license/size/submission rules permit; otherwise include their immutable revision, hashes, attribution, and acquisition command.
