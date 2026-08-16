# Handover: Offline T17–T19 Reporting Build

**Date:** 2026-08-16
**Repo:** `/Users/dmondal/Documents/week-1-fde` (branch at commit `527a222 feat(reports): generate offline latency evidence`)
**Plan:** `docs/superpowers/plans/2026-08-16-offline-reporting.md`
**Design spec:** `docs/superpowers/specs/2026-08-16-offline-reporting-design.md`
**Status:** Task 1 complete & committed. Tasks 2–3 NOT started (paused by user). This doc hands off everything the next session needs.
**Python:** `.venv/bin/python` (3.12.7). Tests: `.venv/bin/python -m pytest -q` → 93 passed.

> TL;DR — a new session should pick up at "## Remaining work: Task 2" below. Everything needed (scaffold, fixtures, ground-truth values, conventions) is documented.

---

## 1. What this session did

1. **Read the authoritative docs** — `PROBLEM_STATEMENT.md`, `RAG_PIPELINE_PLAN.md`, `PROGRESS.md`, `EXPERIMENT_LOG.md`, `TASKS.md`, `AGENTS.md`, the plan and design spec.
2. **Read every relevant source file** — `scripts/evaluation.py`, `scripts/telemetry.py`, `scripts/benchmark.py`, `scripts/pipeline.py`, `scripts/answer_validation.py`, `scripts/retrieval/run.py`, `scripts/retrieval/{bm25,context}.py`, the real T16 run artifacts, the contracts, the eval/v1 fixtures, and all existing tests (`test_evaluation_runner.py`, `test_evaluation_contracts.py`, `test_benchmark.py`, etc.).
3. **Read the three required skills** — `eval-first-rag`, `reducing-llm-latency`, `evaluating-llm-systems` (plus their references).
4. **Ran both analyses in parallel** as subagents — the subagent IPC failed (network reset / context cancel, see §7). Re-ran both analyses inline with `.venv/bin/python` and captured full ground-truth output.
5. **Implemented & committed Task 1** following strict TDD: wrote `tests/test_reporting.py` (failing import) → implemented `scripts/reporting.py` → 5 tests green → committed `527a222`.

## 2. Codebase map (what you need to know)

```
scripts/          # the implementation package (no __init__.py at root; uses namespace pkg)
  evaluation.py   # FROZEN_CONTRACT_ID, FROZEN_THRESHOLDS, REGISTERED_CONDITIONS,
                  #   load_jsonl, validate_trace, write_condition_report,
                  #   grade_retrieval, grade_citations, grade_text_answer,
                  #   summarize_quality, bootstrap_by_case, aligned_waterfalls,
                  #   marginal_stage_percentiles, tail_analysis, build_report_metadata,
                  #   enforce_sealed_holdout, select_frozen_cases, evaluate_promotion
  telemetry.py    # TelemetryTrace — TTC_STAGES, REQUIRED_FIELDS, _PROVENANCE_FIELDS
  benchmark.py    # T16 serial runner (FROZEN_CONDITIONS, validate_conditions,
                  #   select_warmups, validate_preflight, exclusive_lock, main)
  pipeline.py     # run_request (retrieval→Ollama→validate→trace), _file_hash, _prompt
  answer_validation.py  # validate_answer → ValidationResult(valid, citation_ids, fatal_gates)
  retrieval/      # build_index, retrieve, assemble_context, load_manifest
  reporting.py    # *** YOUR MODULE — created this session (Task 1) ***
tests/
  test_reporting.py  # *** YOUR TEST FILE — created this session (Task 1) ***
  test_evaluation_runner.py, test_evaluation_contracts.py, test_benchmark.py  # reference patterns
artifacts/authoritative-runs/20260816T112509Z-1df7268307b1/
  raw-traces.jsonl   # 360 rows (THE SOURCE OF TRUTH)
  validations.jsonl  # 360+ validation records
  warmups.jsonl      # 6 warmup rows (repetition=-1, B0 only)
  run-manifest.json  # C05 gate evidence (status=complete, accepted=true)
eval/v1/            # 24 development_cases.json, holdout_manifest.json (6 sealed), dataset_manifest.json
contracts/          # behavioral_contract.v1.json, thresholds.2026-08-16.json (has latency_budget_p95_ms)
environment/metadata.v1.json  # target environment (M4 Pro, 24 GiB, etc.)
```

### Key conventions observed in the codebase
- **Deterministic everywhere.** Schedules use `seed=20260816`; JSON is always `sort_keys=True`.
- **TDD with fixtures.** Tests build synthetic, schema-faithful fixtures (`tests/test_evaluation_runner.py::_trace`, `tests/test_evaluation_contracts.py::complete_trace`).
- **Three committed conventions to mirror:**
  - `ReportError(ValueError)` raised on invalid inputs (mirrors `BenchmarkError`, `RetrievalError`, `PipelineError`).
  - Hashes are `"sha256:" + hex64` (71-char strings). Files hashed with `hashlib.sha256(path.read_bytes()).hexdigest()`.
  - The manifest is built **last** (after all outputs are written) so `output_hashes` can enumerate every produced file except `report-manifest.json` itself.

## 3. Data schema reference

### Trace row (`raw-traces.jsonl`) — every field you need
| Field | Type | Notes |
|---|---|---|
| `run_id`, `trace_id`, `case_id`, `source_row_id`, `condition_id` | str | provenance |
| `repetition` | int | 0–4 (warmups use -1) |
| `answer_type` | str | one of `boolean`, `numeric_or_date`, `short_phrase`, `free_form` |
| `holdout` | bool | always `false` in dev run |
| `raw_output` | str | JSON: `{"answer": ..., "abstained": bool, "citations": ["SOURCE_N", ...]}`. **Caveat: 35 rows have malformed output** — `answer` is `true` (bool) or unparseable (see §5). |
| `retrieved_evidence_ids` | list[str] | `"passage:N"` format (20 items) |
| `admitted_evidence_ids` | list[str] | top-5 admitted (`"passage:N"`) |
| `retrieved_ranks` | dict[str→int] | passage id → rank |
| `scores` | dict | `{"citation_ids": [int, ...], "validation_valid": bool}`. Malformed → `citation_ids: []`. |
| `fatal_gates` | list[str] | empty for 325 valid rows; `["malformed_output_or_citation_schema"]` for 35. |
| `error_type` | null | always null (no transport errors in this run) |
| `*_ms` stages | float | 6 TTC stages + ttfe/ttft/first_token_displayed/display_finalize. **Stages sum to `ttc_ms`.** |
| `finish_reason` | str | `"stop"` or `"length"` |
| `input_tokens` | null | **always null** (reason: `not_reported_by_model`) |
| `output_tokens` | int | always present (range ~10–60) |
| `dataset_repo`, `corpus_hash`, `index_snapshot`, `model_tag`, `model_digest`, etc. | str | immutable provenance (identical across all 360 rows) |

### Evidence-ID coercion (CRITICAL for graders)
- `retrieved_evidence_ids` / `admitted_evidence_ids` are **strings** `"passage:N"` → must be parsed to `int(N)` before calling `grade_retrieval` / `grade_citations`.
- `gold_evidence_ids` in `development_cases.json` are already **ints** (e.g. `[2828]`).
- `scores.citation_ids` are already **ints**.
- `grade_text_answer` **requires `answer: str`**. For the 35 malformed traces (boolean/unparseable answer), text-answer grades are **unavailable** — do NOT call `grade_text_answer`; report the metric as unavailable/None.

## 4. Task 1 — DONE & committed (`527a222`)

**Files created:**
- `scripts/reporting.py` — `ReportError`, `generate_reports(*, run_dir, output_dir, cases_path=..., holdout_manifest_path=..., thresholds_path=..., seed=SEED, bootstrap_resamples=10_000) -> dict`, plus a `main()` CLI stub (`argparse` — but CLI is Task 3's job; the stub exists but `generate_reports` does NOT yet emit T18/T19/charts).
- `tests/test_reporting.py` — shared `build_synthetic_run()` fixture (360 valid traces, 24 cases, 5 reps) + 5 Task-1 tests.

**What `generate_reports` currently does (Task 1 only):**
1. Refuses a non-empty `output_dir`.
2. Validates the run: 360 attempts, 120/condition, 24 cases, 5 reps, no `holdout: true` in traces, no case_id overlap with the sealed holdout manifest.
3. Loads 24 development cases + 6-case holdout manifest + thresholds file.
4. Calls `scripts.evaluation.write_condition_report(traces, condition_id, output_path=latency.<cond>.json, seed=20260816, resamples=10_000, cases_by_id, command)` for each of the 3 conditions → 3 `latency.*.json` files.
5. Writes `report-manifest.json` with `input_hashes` (run artifacts + cases + holdout + thresholds), `source_run_identity`, `conditions`, `denominators`, `output_hashes`, `command`.

**To run:** `.venv/bin/python -m pytest tests/test_reporting.py -q` (5 passed). Full suite: 93 passed.

**Gap:** `generate_reports` does NOT yet emit `t18-quality-evidence.json`, `t19-evidence.{json,md}`, or the PNG charts. That's Tasks 2–3.

## 5. Ground-truth analysis of the real T16 run (captured this session)

These are the **expected values** a correct implementation should reproduce. Use them as validation anchors. The analysis script read the real run at `artifacts/authoritative-runs/20260816T112509Z-1df7268307b1/` and used the repo's own `grade_retrieval`/`grade_citations`/`grade_text_answer`/`write_condition_report`.

### T18 quality metrics (per condition, all 120 traces each)

| metric | B0_buffered_256 | I1_streaming_256 | I2_buffered_128 |
|---|---|---|---|
| fatal_count | 10 | 10 | 15 |
| recall_at_5 | 0.7917 | 0.7917 | 0.7917 |
| mrr | 0.6477 | 0.6477 | 0.6477 |
| citation_precision | 0.875 | 0.875 | 0.8333 |
| citation_validity_rate | 0.6181 | 0.6181 | 0.6042 |
| task_resolution_rate | 0.2727 | 0.2727 | 0.2857 |
| answer_token_f1 | 0.4278 | 0.4278 | 0.4312 |
| truncation_rate | 0.0 | 0.0 | 0.0417 |

- **Fatal-by-condition:** B0=10, I1=10, I2=15 (total 35, all `malformed_output_or_citation_schema`).
- **B0 and I1 are byte-identical on every quality metric** — expected, since only `stream_mode` differs; the model produces the same output either way.
- **Repetition-zero:** exactly 72 rows (24 cases × 3 conditions), `parity_complete: true` (reps {0,1,2,3,4} present for every case×condition pair).
- **Holdout overlap:** 0 (no `eval-v1-25…30` case_ids in the run).
- **Gate verdict (do NOT decide C06 — just emit inputs):** `fatal_count` ≠ 0 (blocks), and `citation_validity_rate` ≈ 0.6, `task_resolution_rate` ≈ 0.27, `answer_token_f1` ≈ 0.43 — all **below** frozen thresholds (0.98 / 0.85 / 0.80). So the quality gates fail regardless. The 35 malformed boolean answers are the primary driver.

### T19 evidence (from the real run)

- **Budget variance (p95 measured vs `latency_budget_p95_ms`):** ALL stages within budget. Measured p95 TTC is ~1.6–2.1s vs a 15s budget. Largest positive contributor to TTC is `model_dispatch_to_first_token` (~145–2058ms p95 depending on condition).
- **Environment (identical across all 360 rows):** python 3.12.7, macOS 26.5.1 arm64, apple M4 Pro, 25769803776 bytes RAM, power_mode `authoritative-serial`, ollama 0.32.13, model `qwen3:4b-instruct` digest `sha256:0edcdef…f168ba0`, corpus hash `dbe884c2…`, index snapshot `b4942595…`.
- **Tokens:** `input_tokens` = all 360 null, reason `not_reported_by_model`; `tokens_per_second` likewise all null; `output_tokens_total` = **17375** (all 360 present); output_tokens_per_completed_task ≈ 48.3.
- **Spend:** local runtime serving cost = **$0.00** (`FROZEN_THRESHOLDS["external_runtime_api_cost_per_completed_task"]`); agent spend = unavailable (no external API).
- **Interventions (p95, vs B0):**
  - I1 (streaming): `ttc` −266.8 ms, `first_token_displayed` **−917.6 ms** ← the big perceived-latency win.
  - I2 (128 tokens): `ttc` −481.2 ms, `first_token_displayed` −481.2 ms.
  - B0 p95 first_token_displayed ≈ 2066 ms (= TTC, because buffered mode only displays after validation); I1 ≈ 1149 ms (displayed as soon as the first token arrives). This is the **perceived-vs-total latency** distinction the problem statement demands.

### P95 latency by condition (waterfalls.p95)

| condition | ttc_ms | ttft_ms | first_token_displayed_ms |
|---|---|---|---|
| B0_buffered_256 | 2066.28 | 2065.90 | 2066.28 |
| I1_streaming_256 | 1799.46 | 1148.67 | 1148.68 |
| I2_buffered_128 | 1585.08 | 1584.70 | 1585.08 |

### Chart feasibility (verified)
- `matplotlib` 3.11.1 is in `requirements.txt`/`requirements.in`; headless `Agg` backend renders PNGs.
- `Pillow` (PIL) **is** installed in `.venv` → can decode PNG dimensions directly.
- PNG signature = `89504e470d0a1a0a`. IHDR width/height read from bytes 16–24 (big-endian uint32) works as a non-PIL fallback.

## 6. Design decisions & conventions to preserve

These were chosen this session and **must** be honored by Tasks 2–3 to keep the TDD/DRY flow consistent:

1. **Latency reports first, T18/T19 read from them.** `generate_reports` already calls `write_condition_report` (which returns the report dict). Tasks 2–3 should reuse those returned dicts for p95 values rather than re-reading files.
2. **Grader error handling:** wrap `grade_text_answer` so non-string answers (the 35 malformed rows) yield `None` for text metrics rather than crashing. Retrieval/citation grades are always computable (malformed rows contribute 0.0 citation precision from empty `citation_ids`). Quality aggregates use `_mean` that **skips None**.
3. **Quality metrics over all 120 attempts per condition** (not just the `valid` subset that `write_condition_report` uses for waterfalls). `fatal_count` is reported separately. This matches the ground-truth table in §5. (Alternative: restrict to valid traces — either is defensible, but the §5 values came from "all 120" semantics; pick one and document it.)
4. **T18 never decides C06.** Emit every `evaluate_promotion` input (the 10 gate fields + answer-type slices) but do NOT call `evaluate_promotion`/set an `accepted` flag. The plan explicitly says "without deciding C06."
5. **T19 Markdown is rendered FROM the T19 JSON dict** (single source of truth), not recomputed.
6. **Manifest is built last** and hashes all output files (except itself) via `_output_hashes`. Add new outputs and they auto-appear in `output_hashes`.
7. **No secrets/credentials** committed. The `.gitignore` already excludes `.venv/`, `__pycache__/`, datasets. Generated artifacts (`artifacts/reports/...`) are committed per the submission requirements.
8. **TDD pattern:** write failing test → run (confirm fail) → implement → run green → commit. Use the synthetic `build_synthetic_run()` fixture for unit tests; add one real-run integration assertion (skipif the run dir is absent).

## 7. Remaining work: Task 2 (T18 + T19 evidence)

This is the natural pickup point. The plan's Task 2 steps:

- [ ] **2a.** Write failing tests in `tests/test_reporting.py` asserting that `generate_reports` now also writes `t18-quality-evidence.json` and `t19-evidence.{json,md}`. Assert: 72 rep-0 grade records (one per case×condition), 5-rep parity complete, zero holdout overlap, `frozen_gate_inputs` per condition with all 10 keys, `answer_type_deltas_vs_b0` for I1/I2, `frozen_thresholds`, T19 `tokens.input_tokens.available == False` with reason `not_reported_by_model`, `tokens.output_tokens_total` > 0, `spend.local_runtime_serving_cost == 0.0`, `spend.agent_spend.available == False`, `budget_variance` per condition, `environment`, `interventions`.
- [ ] **2b.** Run `.venv/bin/python -m pytest tests/test_reporting.py -q`; verify the new assertions fail (files not yet produced).
- [ ] **2c.** Implement in `scripts/reporting.py`: add `_grade_attempt`, `_aggregate_grades`, `_answer_type_slices`, `_build_t18`, `_build_t19`, `_render_t19_markdown`. Call them inside `generate_reports` after the T17 latency reports and before the manifest. Reuse `grade_retrieval`, `grade_citations`, `grade_text_answer`. Load `contracts/thresholds.2026-08-16.json` for `latency_budget_p95_ms`.
- [ ] **2d.** Run focused tests green; commit `feat(reports): add quality and provenance evidence`.

**Key implementation pointers:**
- Use the fixture's `TEST_THRESHOLDS` (add `latency_budget_p95_ms` to the test thresholds doc — see the budget keys in `contracts/thresholds.2026-08-16.json`).
- `_grade_attempt` id-coercion helper: `"passage:N" → N`; keep ints; skip bools/None (Python `bool` is an `int` subclass — guard with `isinstance(v, bool)`).
- For the markdown, format environment, budget variance table, tokens, spend, and interventions. Assert in the test that a value only in the JSON (e.g. the run_id or `"$0.00"`) appears in the MD.

### Expected T18/T19 values to validate against (real run)
See §5. In particular, the real-run `citation_validity_rate` for B0 is 0.6181 (below the 0.98 gate) and `answer_token_f1` is 0.4278 (below 0.80). These are truthful gate inputs — do not round them away or exclude the malformed rows from citation metrics to "pass" a gate. (Excluding malformed rows from *text* metrics is acceptable and produces the §5 values.)

## 8. Remaining work: Task 3 (charts + CLI + real artifact)

- [ ] **3a.** Write failing tests: PNGs have valid signature `89504e470d0a1a0a`; decodable dimensions > 0; `manifest["chart_metadata"]` values equal the corresponding `latency.*.json` waterfall values (p50/p95 TTC and first_token_displayed per condition).
- [ ] **3b.** Confirm missing-chart assertions fail.
- [ ] **3c.** Implement `_render_charts(output_dir, latency_reports)` → writes `condition-latency.png` (p50/p95 TTC + first-token-displayed per condition, grouped bars) and `waterfalls.png` (stacked p50+p95 stage shares per condition). Return metadata dict; embed under `manifest["chart_metadata"]`. Use `matplotlib.use("Agg")`.
- [ ] **3d.** The `main()` CLI already exists (stub from Task 1) — verify it works end-to-end: `.venv/bin/python -m scripts.reporting --run-dir artifacts/authoritative-runs/20260816T112509Z-1df7268307b1 --output-dir artifacts/reports/20260816T112509Z-1df7268307b1` (defaults for cases/holdout/thresholds resolve from repo root).
- [ ] **3e.** Run the CLI against the real run; verify all 7 output files are produced and hashes land in the manifest.
- [ ] **3f.** Mark T17–T19 complete in `TASKS.md`; run `node .gitnexus/run.cjs detect-changes` (and impact analysis if editing symbols); commit `feat(reports): publish corrected T17 T18 T19 evidence` + the generated `artifacts/reports/...`.

## 9. Validation baseline (run anytime)

```bash
.venv/bin/python -m pytest -q            # 93 passed
.venv/bin/python -m pytest tests/test_reporting.py -q   # 5 passed
```

`/status` is **not available** in this environment (no binary/alias) — consistent with every prior `COLLABORATION_NOTES.md` entry. Record that in any collaboration-note entry per the AGENTS.md template.

## 10. Session note (why subagents were unavailable)

The session was asked to use parallel subagents. Two `subagent` calls were issued in one block for read-only real-run analysis (T18 metrics; T19 evidence + chart feasibility). Both failed: one with `read tcp … connection reset by peer`, the other with `context canceled`. The analyses were re-run **inline** via two parallel `.venv/bin/python` shell calls (see §1). No repo files were written by any subagent. If a future session wants to parallelize, keep subagent tasks strictly read-only (scratch in `/tmp`, never write repo source), disjoint in file ownership, and expect that IPC may be unreliable in this environment — inline shell is the fallback that already worked.
