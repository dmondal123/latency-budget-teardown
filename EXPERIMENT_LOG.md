# Experiment Log

## 2026-08-16 — T16 authoritative development matrix (pre-registered)

- Matrix: 24 frozen development cases × `B0_buffered_256`, `I1_streaming_256`, and `I2_buffered_128` × five repetitions (360 measured attempts), preceded by six excluded development-only baseline warmups.
- Seed: `20260816`; requests are serial and interleaved in seeded thermal blocks. Measured failures are retained and never retried.
- Command: `.venv/bin/python -m scripts.benchmark --conditions B0_buffered_256,I1_streaming_256,I2_buffered_128`.
- Acceptance: 360 attempted rows, 120 rows per condition, complete identities, exclusive benchmark lock, and no sustained swap. Thermal observation is recorded as unavailable because no approved host metric or threshold exists.
- Outcome: completed once. The run manifest reports 360 attempted rows, 360 transport-valid rows, 120 rows per condition, no sustained swap across 1,244 samples, and C05 accepted. Thermal observation is unavailable by the pre-registered policy. Validation fatal gates occurred in 10 B0 rows, 10 I1 rows, and 15 I2 rows; investigate before any intervention decision.

## 2026-08-16 — T20 holdout benchmark (pre-registered)

- Matrix: six sealed holdout cases × `C_accepted` (`B0_buffered_256`, `I1_streaming_256`, `I2_buffered_128`) × five repetitions (90 measured attempts). No warmups; each attempt is measured exactly once.
- `C_accepted` basis: C06 no-regression-vs-baseline slice gate (max_answer_type_slice_regression = 0.05). Measured T18 deltas vs B0 — I1_streaming_256 all 0.0; I2_buffered_128 max 0.0038 (free_form). Both interventions accepted; no holdout outputs were inspected in the decision.
- Seed: `20260816`; requests are serial and interleaved in seeded thermal blocks (same planner as T16).
- Command: `.venv/bin/python -m scripts.benchmark --conditions B0_buffered_256,I1_streaming_256,I2_buffered_128 --holdout`.
- Acceptance: 90 attempted rows, 30 rows per condition, complete identities, exclusive benchmark lock, and no sustained swap. Thermal observation is recorded as unavailable by the pre-registered policy.
- Outcome: completed once. The run manifest reports 90 attempted rows, 90 transport-valid rows, 30 rows per condition, 0 fatal gates, 0 errors, all traces `holdout=true` with `think_mode=False`, no sustained swap across 257 samples, and C07 accepted. Evidence: `artifacts/authoritative-runs/20260816T172257Z-612d93faccd1/`.
