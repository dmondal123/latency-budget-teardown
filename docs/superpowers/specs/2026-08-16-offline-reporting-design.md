# Offline T17–T19 Reporting Design

## Goal

Generate reproducible T17 latency reports and charts, T18 quality evidence,
and T19 budget/provenance evidence exclusively from one immutable T16 run.

## Scope and constraints

- Consume `raw-traces.jsonl`, `validations.jsonl`, `warmups.jsonl`, and
  `run-manifest.json` from an explicit authoritative-run directory.
- Never call Ollama, rerun a benchmark, open sealed holdouts, or mutate the
  input run.
- Preserve the frozen 24-case development denominator, five repetitions, and
  three registered conditions.
- Report fatal validation rows and unavailable cost/token values explicitly;
  never relax a quality gate or invent a measurement.
- Use seed `20260816` and 10,000 case-bootstrap resamples for latency reports.

## Architecture

`scripts.reporting` will be the single offline CLI. It invokes the existing
condition-report writer for each condition, scores one pre-registered
repetition-zero output per development case for T18 while checking all five
repetitions for parity, and writes a trace-linked T19 Markdown evidence report.

The same CLI will render two deterministic PNG charts from the generated JSON:
a p50/p95 TTC and first-token-display comparison, plus percentile-aligned
critical-stage waterfalls. The report directory contains only generated,
run-specific evidence and a machine-readable generation manifest with exact
input hashes and command.

## Outputs

For an explicit output directory, generate:

- `latency.<condition>.json` for every registered condition;
- `t18-quality-evidence.json` with aggregate and answer-type-slice metrics;
- `t19-evidence.md` with budget variance, provenance, environment, tokens,
  spend availability, and intervention evidence;
- `condition-latency.png` and `waterfalls.png`;
- `report-manifest.json`, recording hashes, source run identity, and exact
  command.

## Acceptance criteria

- Reports are deterministic for the same immutable inputs and seed.
- Report metadata identifies the T16 run, corpus/index/model identity, and
  generation command.
- Every report uses 120 attempts per condition and T18 uses 24 development
  outputs per condition without holdout access.
- Chart values are derived only from generated latency JSON, and rendering
  succeeds in the headless local environment.
- Tests cover successful generation, sealed-holdout exclusion, invalid
  denominators, deterministic evidence, and readable chart files.
