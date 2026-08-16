# Authoritative Benchmark Driver Design

## Goal

Provide one deterministic local CLI that can execute T16's authoritative
development matrix against an already-running, preflight-qualified Ollama
service, preserving every attempt and the evidence needed for C05.

## Scope and constraints

- Run exactly the 24 frozen development cases under `B0_buffered_256`,
  `I1_streaming_256`, and `I2_buffered_128`, five times each: 360 measured
  attempts.
- Use seed `20260816`, seeded interleaved thermal blocks, and the existing
  registered single-delta conditions.
- Run six deterministic, excluded baseline warmups selected from development
  cases only; do not read or execute sealed holdouts.
- Require a passing saved Ollama preflight with matching local endpoint,
  model digest, runtime version, and `think=false`; do not start, pull, or
  manage Ollama.
- Run serially with no retries. Persist every scheduled attempt, including
  terminal errors, exactly once.
- Use the existing sustained-swap check across the full run. Thermal state is
  explicitly recorded as unavailable because no approved host thermal metric
  or threshold exists; it is never claimed as validated.
- Preserve the existing manual-query CLI and use the established retrieval,
  validation, telemetry, and report contracts.

## Architecture

Add `scripts.benchmark` as a thin orchestration CLI. It validates immutable
inputs and obtains an exclusive benchmark lock before it constructs the
warmup sequence and calls the existing `run_conditions` scheduler. Its
per-attempt executor uses the existing `run_request` pipeline with frozen
case metadata and condition fields.

`run_request` will become terminal-error-safe: expected retrieval, Ollama,
validation, and telemetry exceptions will result in one observable failure
trace rather than a missing scheduled row. The benchmark module is the sole
owner of run-level concerns: output paths, process locking, preflight
identity comparison, whole-run swap sampling, manifest lifecycle, and C05
integrity summary.

## Artifacts

Each invocation creates a unique directory beneath
`artifacts/authoritative-runs/` containing:

- `raw-traces.jsonl` — the 360 measured rows, appended synchronously;
- `validations.jsonl` — validation records associated by trace ID;
- `warmups.jsonl` — excluded warmup traces, separate from measured rows;
- `run-manifest.json` — command, seed, conditions, warmup IDs, exact input
  identities/hashes, run IDs, attempt/valid/failure denominators, resource
  observations, and C05 status.

The manifest reports `thermal_observation.status` as `unavailable` and gives
the reason. `swap_observation` is a run-level result: it is not retroactively
written into already persisted raw traces. Sustained swap makes C05 fail while
retaining every artifact for truthful reporting.

## Failure behavior

Fail before any request if the preflight artifact, frozen cases, evidence
manifest, or exclusive lock is invalid. After the first measured attempt,
continue the fixed schedule through observable per-attempt failures; do not
retry or replace them. At the end, write the manifest and return nonzero if
the expected count is not 360, provenance is incomplete, sustained swap was
observed, or any C05 integrity rule fails.

An interrupt must leave the rows already flushed and write a manifest with
the actual attempted denominator and an interrupted status. It must not
delete or overwrite an earlier run directory.

## Verification and live-run gate

Focused tests will use a fake request executor and sampler to prove locked
serial scheduling, six excluded warmups, holdout rejection, preflight
mismatch rejection, one-row failure preservation, run-manifest denominators,
swap-block behavior, and interruption handling. Existing pipeline tests will
cover the terminal-error trace contract.

After focused and full tests pass, the operator reviews the exact invocation,
active Ollama identity, available power/ventilation, and planned output path.
Only an explicit approval at that checkpoint authorizes the single live
360-request run. The run is never automatically repeated or extended.
