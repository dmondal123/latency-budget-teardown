# T19 evidence draft — authoritative run `20260816T110727Z-4b3a9c40865b`

**Scope and decision boundary.** This is descriptive evidence for C06 and later reporting, not an intervention-promotion decision. It uses the immutable C05 run inputs under `artifacts/authoritative-runs/20260816T110727Z-4b3a9c40865b/` and their saved, trace-derived condition reports. Quality acceptance, interval interpretation, and accepted-condition selection remain C06 work.

## Provenance and linkage

| Claim | Evidence |
|---|---|
| Run completed with 360 attempted and 360 manifest-valid requests: 120 for each registered condition; no transport failures. | `raw-traces.jsonl` has 360 unique `trace_id` values and one `run_id`; `run-manifest.json` fields `status=complete`, `attempted_count=360`, `valid_count=360`, `failure_count=0`, and `by_condition`. |
| All measured rows are development rows; no holdout output was opened. | `raw-traces.jsonl` field `holdout=false` on all 360 rows. |
| Trace-to-manifest linkage is exact. | Every trace has `run_id=t16-436dad9c3d1b437197744b3a9c40865b`, matching `run-manifest.json.run_id`; reports name the same value in `metadata.run_ids`. |
| Raw evidence integrity at drafting time. | SHA-256: `raw-traces.jsonl` `b12fd103dfce1d2e37cdeac94b7c60886423eab7cf14c6086cde23c673014494`; `validations.jsonl` `ee650115225f393dad9d34c701e752601f9312ec09a1da97d03cca6813f8a1fc`; `warmups.jsonl` `3a7ea3a108af997c9492fc2fcafcf76e0bf47d6974a12e9b0f090996cbf9cd16`; `run-manifest.json` `84300aedaef74fe103d84762fb037b868401c967433c8d4172d497e90629a098`. |
| Reproduction provenance. | `run-manifest.json.command` is `/Users/dmondal/Documents/week-1-fde/scripts/benchmark.py --conditions B0_buffered_256,I1_streaming_256,I2_buffered_128`. Each `latency.*.json` has `metadata.generation_command`, which regenerates that condition report from `raw-traces.jsonl`, development cases, seed `20260816`, and 10,000 resamples. |

## Budget versus measured p95

Budgets are the frozen planning allocations in `RAG_PIPELINE_PLAN.md:241-252`; the figures below are measured marginal-stage p95 values from each report's `marginal_stages.stages.*.p95`. Marginal columns are explicitly non-additive, so they must not be summed. Variance is measured minus budget; a negative number is budget headroom, not an acceptance result.

| Stage (budget ms) | B0 buffered-256 | I1 streaming-256 | I2 buffered-128 |
|---|---:|---:|---:|
| Admission (100) | 0.009 (-99.991) | 0.008 (-99.992) | 0.009 (-99.991) |
| Retrieval (200) | 13.958 (-186.042) | 13.644 (-186.356) | 13.668 (-186.332) |
| Context assembly (300) | 0.057 (-299.943) | 0.056 (-299.944) | 0.064 (-299.936) |
| Dispatch → first token (3,000) | 2,060.498 (-939.502) | 1,766.563 (-1,233.437) | 1,285.657 (-1,714.343) |
| Decode after first token (11,200) | 0.153 (-11,199.847) | 1.204 (-11,198.796) | 0.109 (-11,199.891) |
| Validation (100) | 1.539 (-98.461) | 1.619 (-98.381) | 1.572 (-98.428) |

Whole-request p95 values use the selected percentile-aligned request in `waterfalls.p95`, rather than a sum of marginal stages:

| Metric/budget | B0 buffered-256 | I1 streaming-256 | I2 buffered-128 |
|---|---:|---:|---:|
| TTC (15,000 ms) | 2,068.232 (-12,931.768) | 1,778.692 (-13,221.308) | 1,289.239 (-13,710.762) |
| TTFT (3,900 ms) | 2,066.755 (-1,833.245) | 1,778.195 (-2,121.805) | 1,288.795 (-2,611.205) |
| First token displayed (no separate numeric budget) | 2,068.254 | 1,778.201 | 1,289.244 |

Source fields: `artifacts/reports/20260816T110727Z-4b3a9c40865b/latency.{B0_buffered_256,I1_streaming_256,I2_buffered_128}.json`, `marginal_stages.stages`, `waterfalls.p95.ttc_ms`, `waterfalls.p95.ttft_ms`, and `waterfalls.p95.first_token_displayed_ms`.

Interpretation restricted to measurement: the point-estimate p95 TTC deltas relative to B0 are -289.540 ms for I1 and -778.994 ms for I2; p95 first-token-display deltas are -290.054 ms and -779.011 ms, respectively. `RAG_PIPELINE_PLAN.md:89` specifies that streaming is a perceived-latency intervention and does not make it a TTC win by definition. These deltas do not resolve quality gates or promotion.

## Intervention registration and observed configuration evidence

| Condition | Registered isolated change | Trace evidence | Measured descriptive evidence |
|---|---|---|---|
| `B0_buffered_256` | Reference; no changed field. | `raw-traces.jsonl.condition_id`; all rows have `stream_mode=false`, `cache_state=off`, and `think_mode=false`. | 120 attempts; report `metadata.valid_count=110`. |
| `I1_streaming_256` | Display buffered → streamed. | All rows have `stream_mode=true`; `cache_state=off` and `think_mode=false`. | p95 first-token displayed 1,778.201 ms, versus B0 2,068.254 ms. |
| `I2_buffered_128` | Output-token cap 256 → 128. | All rows have `stream_mode=false`; output-token observations include 128, whereas B0/I1 observed maxima are 151. | p95 TTC 1,289.239 ms, versus B0 2,068.232 ms. |

The registered definitions and required quality checks are in `RAG_PIPELINE_PLAN.md:256-268`. The raw trace evidence supports mode/cap observations but does not itself prove isolated-field enforcement; that is a runner/contract claim, not a measurement claim. No combination condition or holdout run appears in the authoritative trace file.

## Spend and token evidence

| Evidence | Measured/available result | Source |
|---|---|---|
| Output tokens | B0 5,830; I1 5,830; I2 5,715; total 17,375 across 360 attempts. | Sum of `raw-traces.jsonl.output_tokens`, grouped by `condition_id`. |
| Input tokens | Unavailable for all 360 rows; each has `input_tokens=null` and `input_tokens_reason=not_reported_by_model`. | `raw-traces.jsonl.input_tokens` and `input_tokens_reason`. |
| External runtime API serving cost | Frozen target is `$0.00` per completed task because serving is local Ollama; this is a contract/threshold value, not a per-request billing record. | `RAG_PIPELINE_PLAN.md:174-177`; `scripts/evaluation.py` `FROZEN_THRESHOLDS.external_runtime_api_cost_per_completed_task`. |
| Dollar total / cost per completed task | **Unavailable as a measured spend artifact.** There is no provider price, invoice, per-row dollar field, or completed-task cost ledger in the immutable run inputs. | Searched `run-manifest.json`, `raw-traces.jsonl`, `validations.jsonl`, and `warmups.jsonl`; no dollar/spend field. |
| Development-agent spend | **Unavailable.** The plan says it is separate from serving cost, but no amount is recorded in the C05 inputs. | `RAG_PIPELINE_PLAN.md:177`. |

## Model, dependency, and environment identity

Measured trace identity is homogeneous: `qwen3:4b-instruct`; digest `sha256:0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`; Ollama `0.32.13`; Python `3.12.7`; macOS build `macOS-26.5.1-arm64-arm-64bit`; chip `arm64`; RAM `25,769,803,776` bytes; `power_mode=authoritative-serial`; pinned dataset `rag-datasets/rag-mini-wikipedia@1f9f3b53fbc5995b85aab8e993504ad42c5f16f6`; corpus hash `dbe884c22ac0f787287767d5447b18f4172c8ed3e7dd68237206c201d0aa728d`; index snapshot `b494259543f2b3aab92631dd666a2b98967f87e3d9dae4abcff68cb76081c6c7`; contract hash `29ef7dbe28fa646bfd5fc927e744c30f4237dcf7c7d50094903446071913bbf8`. Sources: homogeneous fields on `raw-traces.jsonl` and `run-manifest.json.live_identity`.

The approved environment identity adds Apple M4 Pro, 24 GiB unified memory, AC power, temperature `0`, think mode disabled, local-only `/api/generate` NDJSON, and application lock `requirements.txt`; source `environment/manifest.v1.json:6-41`. The lock is generated with `.venv/bin/python` (`requirements.txt:1-2`); it pins, for example, `datasets==5.0.1` (`:31`), `httpx==0.28.1` (`:57`), `numpy==2.5.2` (`:86`), `rank-bm25==0.2.2` (`:130`), and `pytest==9.1.1` (`:120`).

Resource observations: `run-manifest.json.swap_observation` records 1,244 samples at 250 ms, zero maximum swap, and `sustained_swap=false`. Thermal status is explicitly **unavailable** because no approved host metric or threshold exists (`thermal_observation`). The missing thermal measure must not be presented as a thermal pass.

## Collaboration evidence available in the repository

The repository has a durable collaboration log with correction evidence, including C002 cache-test ambiguity (`COLLABORATION_NOTES.md:44-52`), C003 unsupported multimodal cache assumption (`:54-62`), C004 discovery-command sequencing (`:64-72`), C005 missing impact-analysis workflow (`:74-88`), and C006 missed retrieval requirements caught in review (`:90-104`). For this run, the log records the user-approved serial benchmark and the C05 data outcome at `:302-307`; it also notes the 10/10/15 validation-fatal rows and says latency point estimates cannot support promotion until quality diagnosis.

The C05 run inputs do not contain a model/token `/status` record for the present analysis session, human approval transcript, or dollar-valued agent spend. Those remain unavailable in this draft.

## Re-run and validation commands used for this draft

```bash
jq -s 'group_by(.condition_id)[] | {condition: .[0].condition_id, count:length, output_tokens_total:(map(.output_tokens // 0)|add), input_tokens_null:(map(select(.input_tokens==null))|length)}' artifacts/authoritative-runs/20260816T110727Z-4b3a9c40865b/raw-traces.jsonl
jq -r '[.metadata.condition_id, .waterfalls.p95.ttc_ms, .waterfalls.p95.ttft_ms, .waterfalls.p95.first_token_displayed_ms] | @tsv' artifacts/reports/20260816T110727Z-4b3a9c40865b/latency.*.json
jq -r '.metadata.condition_id as $c | .marginal_stages.stages | to_entries[] | [$c,.key,.value.p95] | @tsv' artifacts/reports/20260816T110727Z-4b3a9c40865b/latency.*.json
shasum -a 256 artifacts/authoritative-runs/20260816T110727Z-4b3a9c40865b/{raw-traces.jsonl,validations.jsonl,warmups.jsonl,run-manifest.json}
```

The original benchmark and condition-report commands are recorded in `run-manifest.json.command` and each report's `metadata.generation_command`, respectively. This task did not rerun the benchmark, profiling, or Ollama.
