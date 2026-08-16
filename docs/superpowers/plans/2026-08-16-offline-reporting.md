# Offline T17–T19 Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate reproducible offline T17 latency reports/charts, T18 quality/gate inputs, and T19 provenance evidence from the corrected T16 run.

**Architecture:** Add `scripts.reporting` as one offline CLI. It validates fixed inputs, uses `scripts.evaluation.write_condition_report` for T17, scores the prescribed repetition-zero output for T18, derives T19 from saved evidence, then renders charts from latency JSON only.

**Tech Stack:** Python 3.12, stdlib JSON/hashlib, Matplotlib, existing evaluation helpers, pytest.

## Global Constraints

- Never call Ollama, benchmark, or access sealed holdouts.
- Require 360 saved rows, 120 per registered condition, 24 development cases, and five repetitions.
- Use seed `20260816` and 10,000 case-bootstrap resamples.
- Refuse non-empty output directories and report unavailable values rather than inventing data.

---

### Task 1: Validate run inputs and generate T17 reports

**Files:**
- Create: `scripts/reporting.py`
- Create: `tests/test_reporting.py`

**Interfaces:** `generate_reports(*, run_dir: Path, output_dir: Path) -> dict[str, object]` loads verified inputs and writes one latency JSON per registered condition plus `report-manifest.json`.

- [ ] Write a failing fixture-backed test that verifies a 360-row run creates three reports with 120 attempts each and source hashes for run artifacts, development cases, holdout manifest, and thresholds.
- [ ] Run `.venv/bin/python -m pytest tests/test_reporting.py -q`; verify the expected import failure.
- [ ] Implement input/denominator/holdout/output-directory validation, invoke `write_condition_report` with the frozen seed and 10,000 resamples, and write the manifest.
- [ ] Run the focused test and commit `feat(reports): generate offline latency evidence`.

### Task 2: Generate T18 and T19 machine-readable evidence

**Files:**
- Modify: `scripts/reporting.py`
- Modify: `tests/test_reporting.py`

**Interfaces:** The report directory gains `t18-quality-evidence.json`, `t19-evidence.json`, and `t19-evidence.md`.

- [ ] Write failing tests for one repetition-zero row per development case/condition, five-repetition parity, zero holdout overlap, frozen gate inputs, answer-type deltas from B0, explicit token/dollar availability, and `$0.00` local serving cost.
- [ ] Run the focused tests; verify the missing-evidence assertions fail.
- [ ] Reuse `grade_retrieval`, `grade_citations`, and `grade_text_answer`; compute all threshold inputs without C06 promotion; render Markdown only from the T19 JSON evidence.
- [ ] Run focused tests and commit `feat(reports): add quality and provenance evidence`.

### Task 3: Render charts, execute, and validate artifacts

**Files:**
- Modify: `scripts/reporting.py`
- Modify: `tests/test_reporting.py`
- Modify: `TASKS.md`
- Create: `artifacts/reports/20260816T112509Z-1df7268307b1/`

**Interfaces:** CLI: `.venv/bin/python -m scripts.reporting --run-dir PATH --output-dir PATH`; generated charts: `condition-latency.png`, `waterfalls.png`.

- [ ] Write failing tests that PNG signatures and decoded dimensions are valid, and chart metadata equals generated latency JSON values.
- [ ] Run the focused tests; verify missing chart assertions fail.
- [ ] Render headless Matplotlib charts from generated JSON, add the CLI, hash every output into the manifest, then run full tests and the CLI against the corrected T16 run.
- [ ] Mark T17–T19 complete in `TASKS.md`, run `detect_changes`, and commit `feat(reports): publish corrected T17 T18 T19 evidence`.
