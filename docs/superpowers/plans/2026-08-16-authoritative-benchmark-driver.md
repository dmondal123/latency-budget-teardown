# Authoritative Benchmark Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible serial CLI that executes T16's 360 development attempts against the already-running qualified Ollama service, persists every attempt, and emits C05 integrity evidence.

**Architecture:** `scripts.benchmark` owns immutable-input validation, live Ollama identity comparison, warmups, exclusive process locking, serial scheduling, raw-trace writes, whole-run swap observation, artifact directories, and the run manifest. It delegates individual attempts to the existing retrieval → Ollama → validation path. `scripts.pipeline.run_request` is made terminal-error-safe so an expected request failure becomes one observable row rather than a missing matrix row.

**Tech Stack:** Python 3.12, standard library (`argparse`, `fcntl`, `json`, `signal`, `uuid`), existing Ollama client, telemetry, BM25 retrieval, and pytest.

## Global Constraints

- Use only the frozen development cases, seed `20260816`, five repetitions, and `B0_buffered_256`, `I1_streaming_256`, `I2_buffered_128`; reject holdout execution.
- Execute one request at a time; do not retry, replace, or automatically extend a measured attempt.
- Require an already-running loopback Ollama service that matches the saved passing preflight. Do not start, pull, stop, or otherwise manage Ollama.
- Preserve all completed rows on ordinary errors and `SIGINT`/`SIGTERM`; never overwrite a prior authoritative-run directory.
- Use the existing whole-run sustained-swap rule. Record thermal observation as unavailable with its reason; never report a thermal pass.
- Keep the user’s existing changes to `AGENTS.md` and `CLAUDE.md` untouched.
- Before editing a function, class, or method, run GitNexus upstream impact analysis and warn the user if its risk is HIGH or CRITICAL.
- Before each commit, update `TASKS.md`, run GitNexus `detect_changes()`, and record a significant decision/correction in `COLLABORATION_NOTES.md` when applicable.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `scripts/pipeline.py` | Convert expected in-flight request exceptions into one terminal-error row and let the caller select trace persistence without changing successful manual-query behavior. |
| `scripts/benchmark.py` | New authoritative-run CLI, frozen input checks, serial execution, lock, artifact/manifest lifecycle, and exit status. |
| `tests/test_pipeline.py` | Regression coverage for a failed request that still produces one trace row. |
| `tests/test_benchmark.py` | Unit and CLI-level contracts for the driver using fake clients/executors and samplers only. |
| `README.md` | Document the real authoritative command, prerequisites, artifact paths, and interruption semantics. |
| `TASKS.md`, `PROGRESS.md`, `EXPERIMENT_LOG.md` | Record implementation completion, T16 registration/execution truthfully, and C05 outcome after the live run. |

### Task 1: Preserve terminal-error attempts in the request path

**Files:**

- Modify: `scripts/pipeline.py:39-103`
- Modify: `tests/test_pipeline.py`

**Interfaces:**

- Consumes: existing `run_request(...) -> dict[str, Any]` inputs.
- Produces: the same successful trace row as today, or an error row with `error_type`, unavailable-value reasons, and no invented completion spans. The new `persist_trace: bool = True` argument preserves the manual CLI's append behavior and lets the benchmark own raw-trace appends.
- Depends on: `TelemetryTrace.terminal_error()`, `TelemetryTrace.cli_returned()`, and `TelemetryTrace.persist_jsonl()`.

- [ ] **Step 1: Write failing request-error regression tests.**

```python
def test_pipeline_persists_one_terminal_error_trace_when_ollama_fails(tmp_path, index):
    client = OllamaClient(transport=lambda *_: (_ for _ in ()).throw(OllamaClientError("service_unavailable")))
    row = run_request(
        question="What is the capital of France?", index=index, client=client,
        raw_fields=raw_fields(index, condition_id="B0_fixture"),
        trace_path=tmp_path / "trace.jsonl", validation_path=tmp_path / "validation.jsonl",
    stream_mode=False, persist_trace=True,
    )
    assert row["error_type"] == "ollama_client_error"
    assert len((tmp_path / "trace.jsonl").read_text().splitlines()) == 1
    assert row["ttc_ms"] is None
    assert row["ttc_ms_reason"] == "unavailable_due_to_terminal_error"
```

- [ ] **Step 2: Run the focused test and confirm the current behavior fails by raising instead of returning a row.**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py::test_pipeline_persists_one_terminal_error_trace_when_ollama_fails -q`  
Expected: FAIL because `OllamaClientError` escapes `run_request`.

- [ ] **Step 3: Run required GitNexus impact analysis before editing `run_request`.**

Run: GitNexus `impact({target: "run_request", file_path: "scripts/pipeline.py", direction: "upstream", repo: "latency-budget-teardown"})`.  
Expected: inspect direct callers (`main` and focused tests); stop and request direction if risk is HIGH or CRITICAL.

- [ ] **Step 4: Implement the smallest error-to-trace boundary.**

Wrap only the operations after `TelemetryTrace` construction in `try/except` for `OllamaClientError`, `RetrievalError`, `PipelineError`, and narrowly scoped `OSError` from request/file operations. Map classes to stable snake-case strings, call `trace.terminal_error(error_type)` and `trace.cli_returned()`, then either append the row when `persist_trace` is true or return `trace.to_row()` when false. Do not catch `ValueError`/`TelemetryError`, `KeyboardInterrupt`, `SystemExit`, or unexpected programming errors. Leave the successful manual-query return path unchanged.

```python
except (OllamaClientError, RetrievalError, PipelineError, OSError) as exc:
    trace.terminal_error(_error_type(exc))
    trace.cli_returned()
    return trace.persist_jsonl(trace_path) if persist_trace else trace.to_row()
```

- [ ] **Step 5: Verify focused pipeline and telemetry contracts.**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py tests/test_telemetry.py -q`  
Expected: PASS, including the new error-row assertion and existing successful streamed/buffered behavior.

- [ ] **Step 6: Update tracking and commit the self-contained failure-preservation change.**

Update `TASKS.md` with the completed terminal-error persistence subtask. Run GitNexus `detect_changes({scope: "all", repo: "latency-budget-teardown"})`, review that only `run_request` and its tests affect the expected pipeline flow, then commit:

```bash
git add scripts/pipeline.py tests/test_pipeline.py TASKS.md
git commit -m "fix(pipeline): preserve terminal benchmark failures"
```

### Task 2: Build frozen benchmark inputs, lock, and manifest primitives

**Files:**

- Create: `scripts/benchmark.py`
- Create: `tests/test_benchmark.py`

**Interfaces:**

- Produces `load_development_cases(path: Path) -> list[dict[str, Any]]`, `select_warmups(cases, seed) -> list[dict[str, Any]]`, `validate_preflight(preflight, expected) -> dict[str, Any]`, `exclusive_lock(path: Path) -> ContextManager[None]`, and `write_manifest(path, manifest) -> None`.
- Consumes: `eval/v1/development_cases.json`, `artifacts/ollama_preflight.v1.json`, `artifacts/text_evidence_manifest.v1.json`, the behavioral contract, and registered conditions.

- [ ] **Step 1: Write failing tests for frozen inputs and six warmups.**

```python
def test_warmups_are_seeded_baseline_only_and_never_include_holdouts():
    warmups = select_warmups(development_cases(), seed=20260816)
    assert len(warmups) == 6
    assert all(case["holdout"] is False for case in warmups)
    assert {case["answer_type"] for case in warmups} == {
        "boolean", "numeric_or_date", "short_phrase", "free_form"
    }

def test_preflight_rejects_digest_mismatch():
    with pytest.raises(BenchmarkError, match="model digest"):
        validate_preflight(passing_preflight(model_digest="different"), expected_identity())
```

- [ ] **Step 2: Run the new tests to confirm imports/functions are missing.**

Run: `.venv/bin/python -m pytest tests/test_benchmark.py -q`  
Expected: FAIL during collection because `scripts.benchmark` does not exist.

- [ ] **Step 3: Implement deterministic input validation.**

Require exactly 24 case objects, unique `case_id` values, `holdout is False`, the expected 6/6/6/6 answer-type allocation, and all question/reference/evidence fields used downstream. Select one sorted, seed-shuffled case per answer type, then select two additional seed-shuffled unused cases; shuffle the six selected warmups with the same local RNG. Warmups always use `B0_buffered_256` and are recorded separately.

Validate `preflight["status"] == "pass"`, `local_only is True`, `think is False`, `resource_checks.sustained_swap is False`, the loopback endpoint, and exact model digest/runtime version equality with the saved environment/preflight identity. Query the already-running loopback service immediately before warmups with `scripts.preflight_ollama.version(endpoint, timeout)` and `model_digest(endpoint, model, timeout)`; reject a runtime or digest mismatch without sending a generation request.

- [ ] **Step 4: Implement single-process and manifest primitives.**

Use `fcntl.flock(lock_file.fileno(), LOCK_EX | LOCK_NB)` against `artifacts/authoritative-runs/.benchmark.lock`; raise `BenchmarkError("another authoritative benchmark is running")` on `BlockingIOError`. Create a unique output directory as `artifacts/authoritative-runs/<UTC timestamp>-<uuid4 hex>` and reject an existing path. Write JSON with sorted keys to a temporary sibling then `Path.replace()` it. Record the lock path, PID, acquisition timestamp, and release timestamp in the manifest; this records the driver's exclusion mechanism and does not claim to observe arbitrary external processes.

The initial manifest status is `running`; its fixed resource section is:

```json
{
  "thermal_observation": {
    "status": "unavailable",
    "reason": "no approved host thermal metric or threshold"
  },
  "swap_observation": {"status": "running"}
}
```

- [ ] **Step 5: Verify all primitive contracts.**

Run: `.venv/bin/python -m pytest tests/test_benchmark.py -q`  
Expected: PASS for malformed cases, sealed holdout rejection, deterministic warmups, mismatched preflight, lock contention, and atomic manifest content.

- [ ] **Step 6: Commit the independently testable primitive layer.**

Update `TASKS.md`, run GitNexus `detect_changes({scope: "all", repo: "latency-budget-teardown"})`, then commit:

```bash
git add scripts/benchmark.py tests/test_benchmark.py TASKS.md
git commit -m "feat(benchmark): validate frozen run inputs"
```

### Task 3: Execute the serial matrix and create C05 evidence

**Files:**

- Modify: `scripts/benchmark.py`
- Modify: `tests/test_benchmark.py`

**Interfaces:**

- Produces `run_benchmark(config: BenchmarkConfig, *, execute_attempt: Callable[..., Mapping[str, Any]] = ...) -> dict[str, Any]` and CLI `main(argv: list[str] | None = None) -> int`.
- Consumes: Task 2 primitives, `scripts.evaluation.run_conditions`, `REGISTERED_CONDITIONS`, `scripts.pipeline.run_request`, and `SwapSampler`.
- Produces: `raw-traces.jsonl`, `validations.jsonl`, `warmups.jsonl`, and a terminal `run-manifest.json`. `run_benchmark` is the sole raw-JSONL appender; every injected executor returns one in-memory row.

- [ ] **Step 1: Write failing schedule, persistence, and C05 tests.**

```python
def test_run_benchmark_writes_360_serial_attempts_and_explicit_denominators(tmp_path):
    result = run_benchmark(config_for(tmp_path), execute_attempt=fake_success)
    manifest = json.loads((result["run_dir"] / "run-manifest.json").read_text())
    assert manifest["attempted_count"] == 360
    assert manifest["by_condition"] == {
        "B0_buffered_256": 120, "I1_streaming_256": 120, "I2_buffered_128": 120
    }
    assert len(read_jsonl(result["run_dir"] / "raw-traces.jsonl")) == 360
    assert manifest["c05"]["accepted"] is True

def test_run_benchmark_retains_failures_and_marks_sustained_swap_invalid(tmp_path):
    result = run_benchmark(config_for(tmp_path), execute_attempt=fake_one_failure, sampler=FakeSampler(True))
    assert result["manifest"]["attempted_count"] == 360
    assert result["manifest"]["failure_count"] == 1
    assert result["manifest"]["c05"]["accepted"] is False
    assert "sustained_swap" in result["manifest"]["c05"]["blocking_categories"]
```

- [ ] **Step 2: Run these tests and confirm the orchestration API is not implemented.**

Run: `.venv/bin/python -m pytest tests/test_benchmark.py -q`  
Expected: FAIL because `run_benchmark` and `BenchmarkConfig` are missing.

- [ ] **Step 3: Implement the serial executor.**

Parse `--conditions` as a comma-separated list and require the exact ordered sequence `B0_buffered_256,I1_streaming_256,I2_buffered_128`; reject duplicates, omissions, additions, and reorderings. Build the index once, construct immutable raw fields per scheduled case using a new non-manual provenance helper, and use `run_conditions(case_ids=..., condition_ids=(...), repetitions=5, seed=20260816, execute=...)`. The executor must call `run_request(..., persist_trace=False)` once using the condition’s `stream_mode`, `max_tokens`, retrieval values, shared client, and validation path, then synchronously append that returned row to `raw-traces.jsonl`. Injected fake executors return rows only; `run_benchmark` appends them through the same helper. Include the complete schedule mapping in the manifest rather than mutating an already-created trace row.

Run six baseline warmups before the measured schedule; invoke the same executor with `persist_trace=False` and append their rows only to `warmups.jsonl`. Start `SwapSampler` before warmups and stop it in `finally`. Do not set a final sustained-swap result on already-persisted rows; write it only to the terminal manifest.

- [ ] **Step 4: Implement terminal manifest and exit predicates.**

The terminal manifest must contain `status`, `run_id`, exact command, case/contract/index hashes, preflight identity, warmup case IDs, condition configurations, attempted/valid/failure counts, counts by condition, actual schedule count, `swap_observation`, `thermal_observation`, and:

```python
def c05_summary(rows, swap_observation):
    blockers = []
    if len(rows) != 360: blockers.append("attempt_count")
    if any(count != 120 for count in counts_by_condition.values()): blockers.append("condition_denominator")
    if any(not complete_identity(row) for row in rows): blockers.append("incomplete_identity")
    if swap_observation["sustained_swap"] is not False: blockers.append("sustained_swap")
    return {"accepted": not blockers, "blocking_categories": blockers}
```

The CLI returns `0` only for a complete C05-accepted run, `1` for completed-but-invalid evidence, `2` for preflight/input/lock failure, and `130` for an interrupted run. A `SIGINT` or `SIGTERM` updates the manifest to `interrupted`, preserves actual denominators, releases the lock, and does not retry pending attempts.

- [ ] **Step 5: Verify the driver with no live Ollama requests.**

Run: `.venv/bin/python -m pytest tests/test_benchmark.py tests/test_evaluation_runner.py tests/test_evaluation_contracts.py -q`  
Expected: PASS, including 360 fake attempts, all failure rows preserved, lock exclusion, manifest fields, and sustained-swap C05 rejection.

- [ ] **Step 6: Commit the completed benchmark driver.**

Update `TASKS.md`; add a concise `COLLABORATION_NOTES.md` entry if implementation exposes a correction. Run GitNexus `detect_changes({scope: "all", repo: "latency-budget-teardown"})`, verify the affected flow is the benchmark/pipeline path only, then commit:

```bash
git add scripts/benchmark.py tests/test_benchmark.py TASKS.md COLLABORATION_NOTES.md
git commit -m "feat(benchmark): run authoritative matrix serially"
```

### Task 4: Document the operational contract and validate the implementation

**Files:**

- Modify: `README.md:55-77`
- Modify: `TASKS.md`
- Modify: `PROGRESS.md`
- Test: `tests/test_benchmark.py`

**Interfaces:**

- Consumes: Task 3’s CLI and artifact format.
- Produces: a documented, reproducible command and an accurate readiness state before live measurement.

- [ ] **Step 1: Write a failing CLI/help regression test.**

```python
def test_benchmark_help_names_the_three_registered_conditions(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert "B0_buffered_256" in capsys.readouterr().out
```

- [ ] **Step 2: Run the focused test and confirm the documented public contract is absent or incomplete.**

Run: `.venv/bin/python -m pytest tests/test_benchmark.py::test_benchmark_help_names_the_three_registered_conditions -q`  
Expected: FAIL until the CLI parser exposes its registered condition list.

- [ ] **Step 3: Document the exact pre-live command and safeguards.**

Add this command to `README.md`, with prerequisites that Ollama is already running, the preflight is passing, the host is on power/ventilated, and no competing benchmark is running:

```bash
.venv/bin/python -m scripts.benchmark \
  --conditions B0_buffered_256,I1_streaming_256,I2_buffered_128
```

Document the output directory, 360-attempt matrix, six excluded warmups, no-retry policy, ordinary-interrupt preservation, whole-run swap gate, and the explicit thermal-unavailable limitation. Do not mark T16 or C05 complete at this stage.

- [ ] **Step 4: Run focused, full, and static validations.**

Run:

```bash
.venv/bin/python -m pytest tests/test_pipeline.py tests/test_telemetry.py tests/test_benchmark.py tests/test_evaluation_runner.py tests/test_evaluation_contracts.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.benchmark --help
git diff --check
```

Expected: all tests pass, help succeeds without contacting Ollama, and the diff has no whitespace errors.

- [ ] **Step 5: Commit the verified operational documentation.**

Update `TASKS.md` to mark the implementation/readiness subtask complete while leaving T16/C05 unchecked. Run GitNexus `detect_changes({scope: "all", repo: "latency-budget-teardown"})`, then commit:

```bash
git add README.md TASKS.md PROGRESS.md tests/test_benchmark.py
git commit -m "docs(benchmark): document authoritative run"
```

### Task 5: Human live-run checkpoint and one authoritative execution

**Files:**

- Modify: `EXPERIMENT_LOG.md`
- Modify: `TASKS.md`
- Modify: `PROGRESS.md`
- Modify: `COLLABORATION_NOTES.md` only if a significant correction or decision occurs.

**HITL checkpoint:** Human operator reviews the exact command, passing preflight identity, output directory, power/ventilation, no competing benchmark process, and the expected 1.5–2 hour duration. The operator must explicitly say: **“Yes, start the live T16 benchmark.”** Do not run the command without that sentence.

- [ ] **Step 1: Pre-register the live run without fabricating results.**

Add a concise `EXPERIMENT_LOG.md` entry naming the 360-request development matrix, six excluded warmups, three immutable conditions, seed, exact command, acceptance checks, and the thermal-unavailable/swap-gated resource policy. Leave outcome fields pending.

- [ ] **Step 2: Re-run only non-load preflight checks.**

Run:

```bash
.venv/bin/python scripts/verify_environment.py
.venv/bin/python scripts/verify_eval.py --repo-root .
.venv/bin/python -m scripts.benchmark --help
```

Expected: all pass without launching benchmark load.

- [ ] **Step 3: Obtain the explicit live-run approval.**

Record the user’s exact approval in the session and proceed only after it is received.

- [ ] **Step 4: Run T16 once, serially.**

Run:

```bash
.venv/bin/python -m scripts.benchmark \
  --conditions B0_buffered_256,I1_streaming_256,I2_buffered_128
```

Do not run parallel load, retry a failure, replace a row, or extend the run automatically. If interrupted or C05 fails, retain the artifacts and report actual denominators.

- [ ] **Step 5: Validate C05 from immutable artifacts.**

Verify raw JSONL count, all 24×3×5 schedule combinations, exact 120-attempt condition denominators, valid/failure denominators, complete run identities, lock history, and final swap observation. Confirm the manifest records thermal observation as unavailable, not passing. Update `TASKS.md`/`PROGRESS.md` accurately: mark T16/C05 complete only if their evidence holds.

- [ ] **Step 6: Commit the truthful measurement evidence.**

Update `EXPERIMENT_LOG.md` with exact artifact paths, command, raw counts, C05 outcome, and no interpretation beyond the evidence. Run GitNexus `detect_changes({scope: "all", repo: "latency-budget-teardown"})`, then commit the logs/tracking and authoritative artifacts only if they meet the repository’s submission-size and provenance rules:

```bash
git add EXPERIMENT_LOG.md TASKS.md PROGRESS.md COLLABORATION_NOTES.md artifacts/authoritative-runs
git commit -m "data(benchmark): record T16 matrix"
```

## Self-review

- Coverage: Tasks 1–4 implement and prove failure preservation, frozen input checks, warmups, serial interleaving, process exclusion, whole-run swap gating, artifact persistence, CLI documentation, and full tests. Task 5 performs the only live run after an explicit approval.
- Requirement alignment: the plan preserves the 24×3×5 matrix, C05 denominators, preflight identity, no-retry rule, and development/holdout isolation. It deliberately records thermal state as unavailable instead of asserting a false thermal check.
- Type consistency: `run_request` remains `-> dict[str, Any]`; Task 3 adds `BenchmarkConfig` and `run_benchmark` before Task 4/5 reference them.
- Scope: no retrieval/model intervention, holdout execution, reporting decision, packaging, or Ollama lifecycle management is introduced.
