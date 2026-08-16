# Experiment Log

## 2026-08-16 — T16 authoritative development matrix (pre-registered)

- Matrix: 24 frozen development cases × `B0_buffered_256`, `I1_streaming_256`, and `I2_buffered_128` × five repetitions (360 measured attempts), preceded by six excluded development-only baseline warmups.
- Seed: `20260816`; requests are serial and interleaved in seeded thermal blocks. Measured failures are retained and never retried.
- Command: `.venv/bin/python -m scripts.benchmark --conditions B0_buffered_256,I1_streaming_256,I2_buffered_128`.
- Acceptance: 360 attempted rows, 120 rows per condition, complete identities, exclusive benchmark lock, and no sustained swap. Thermal observation is recorded as unavailable because no approved host metric or threshold exists.
- Outcome: completed once. The run manifest reports 360 attempted rows, 360 transport-valid rows, 120 rows per condition, no sustained swap across 1,244 samples, and C05 accepted. Thermal observation is unavailable by the pre-registered policy. Validation fatal gates occurred in 10 B0 rows, 10 I1 rows, and 15 I2 rows; investigate before any intervention decision.
