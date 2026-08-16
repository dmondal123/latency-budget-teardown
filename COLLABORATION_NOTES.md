# Collaboration Notes

This file records how the human and AI worked together, especially decisions, corrections, rejected assumptions, approval gates, and changes in direction. It is not a transcript. Keep entries short, factual, and linked to repository evidence.

Update this file only after a significant decision, correction, failure investigation, changed direction, or reusable learning. It is not a per-commit or per-task journal. Before every commit, run `/status`; include the reported token use and model only when the related work merits an entry. If nothing significant happened, do not update this file. The final submission must include at least two cases where the agent was wrong or suboptimal and explain how the issue was caught and corrected.

## Working agreement

| Topic | Agreement |
|---|---|
| Requirements | `PROBLEM_STATEMENT.md` is authoritative |
| Implementation plan | `RAG_PIPELINE_PLAN.md` is approved as of 2026-08-16 |
| Human approval | Required at the measurement-contract, baseline-integrity, intervention-decision, and final-delivery gates |
| Metrics | Only reproducible script output may appear as measured evidence |
| Experiments | Register before execution and log immediately in `EXPERIMENT_LOG.md` |
| Progress | Update `PROGRESS.md` after meaningful milestones or blockers |
| Corrections | Preserve the original issue, how it was found, and the resulting preventive rule |
| Entry threshold | Log only significant decisions, corrections, failures, direction changes, or reusable learnings |
| Commit metadata | Run `/status` before every commit; record its token use and model only in significant related entries |

## Decision and correction index

| ID | Date | Type | Summary | Evidence |
|---|---|---|---|---|
| C001 | 2026-08-16 | Human approval | Approved the structure-first RAG pipeline plan | `RAG_PIPELINE_PLAN.md` |
| C002 | 2026-08-16 | Agent correction | Replaced ambiguous cache testing with separate application-cache and engine-prefix-cache policies | `RAG_PIPELINE_PLAN.md` sections 3, 8, and 9 |
| C003 | 2026-08-16 | Agent correction | Changed multimodal prefix caching from an assumption to a correctness-gated policy | `RAG_PIPELINE_PLAN.md` section 8 |
| C004 | 2026-08-16 | Agent correction | Stopped a failed discovery command from suppressing later checks by running checks independently | Collaboration session evidence |
| C005 | 2026-08-16 | Agent correction | Added the missing dedicated GitNexus impact-analysis workflow and logged the contract/eval approval boundary | `scripts/verify_eval.py`, GitNexus analysis output, `PROGRESS.md` |
| C006 | 2026-08-16 | Agent correction | Revised Task 6 after review-plan found missing assembly bounds and durable citation identity | `scripts/retrieval.py`, `tests/test_retrieval.py` |

## Detailed entries

### C001: Structure-first plan approval

Context: The human asked for the pipeline stages, baseline metrics, p50/p95 waterfall, quality gates, two isolated interventions, and budget methodology to be established before implementation. The human also asked for vLLM-Metal-specific latency exploration.

Agent contribution: Reviewed the existing plan using the evaluation and latency skills, checked current vLLM-Metal primary sources, and proposed a structure-first rewrite.

Human decision: Explicitly approved the structure-first rewrite and then approved the refined plan.

Result: `RAG_PIPELINE_PLAN.md` is the implementation authority. It remains subject to the approval gates inside the plan.

### C002: Cache experiment ambiguity

What was suboptimal: The earlier plan used a generic cache off/on condition and placed a unique nonce at the start of every prompt. That design mixed application caching with vLLM prefix caching and would have removed representative shared-prefix reuse.

How it was caught: The agent compared the plan with current vLLM-Metal defaults and upstream vLLM prefix-cache behavior during the source-backed review.

Correction: The plan now separates application caches from engine KV-prefix caching. The nonce begins only at the dynamic user/evidence portion, leaving the stable system contract eligible for realistic reuse. Cache-hit tokens must be measured.

Preventive rule: Name every cache layer, record its state independently, and never use a benchmark anti-cache mechanism without stating which reuse it invalidates.

### C003: Experimental multimodal prefix-cache assumption

What was wrong: The first rewrite treated automatic prefix caching as safe for every primary Qwen3-VL condition. Upstream vLLM supports multimodal cache hashing, but the vLLM-Metal Qwen3-VL path is experimental, so upstream capability alone did not prove Metal-path correctness.

How it was caught: A post-edit source audit distinguished upstream cache design from the selected experimental hardware plugin path.

Correction: Prefix caching now requires same-text/different-image, repeated-image, concurrency-2, and cache-disabled parity probes. The resulting policy is frozen across product interventions. A failed gate keeps prefix caching disabled and preserves the incompatibility as evidence.

Preventive rule: Do not infer plugin support from upstream framework support. Require a target-backend correctness probe before performance testing.

### C004: Discovery command sequencing

What was suboptimal: A repository-discovery command chained `git log` with later read-only checks. Because the new repository had no commits, `git log` exited nonzero and prevented the remaining checks from running.

How it was caught: The command output ended at the empty-history error and lacked the expected status and search results.

Correction: Later discovery and validation checks were run independently, so an expected absence in one source could not suppress unrelated evidence.

Preventive rule: Run independent discovery checks independently. Treat an empty Git history as valid repository state.

### C005: Eval milestone governance and impact analysis

Context: The behavioral contract, dated thresholds, evaluation schema, 24 development cases, six holdouts, verifier, and tests were added in commit `8c411ee`.

What was suboptimal: The commit ran the GitNexus CLI `detect-changes` check but did not complete the dedicated impact-analysis workflow. The milestone also had not been recorded here despite adding a draft/pending-G1 boundary that materially affects benchmark governance.

How it was caught: The human asked whether the GitNexus analysis skill had been used for each commit and pointed out the missing collaboration-note update.

Correction: Refreshed the GitNexus index, analyzed `validate_cases` upstream, reviewed the process inventory, and re-ran `detect-changes`. The analysis reports one direct caller (`main`), one affected process, and LOW risk. `PROGRESS.md` correctly keeps M03 and M04 in progress pending G1 rather than marking them complete.

Evidence: `node .gitnexus/run.cjs analyze`; `node .gitnexus/run.cjs impact validate_cases --direction upstream`; `node .gitnexus/run.cjs detect-changes`; `scripts/verify_eval.py`; `PROGRESS.md`.

`/status` model and token use: unavailable in this API session.

Preventive rule: For every non-trivial commit, complete the matching GitNexus workflow—not only `detect-changes`—and add a concise collaboration entry when an implementation changes an approval boundary or corrects the operating process.

### C006: Task 6 review-plan correction

Context: The initial Task 6 implementation outline covered BM25, packing, and citation binding but did not explicitly cover every requirement in the approved retrieval/context-assembly sequence.

What was suboptimal: The outline omitted an explicit two-page bound, durable document hash in citation metadata, and an observable model-dispatch abstention check.

How it was caught: The `review-plan` coverage audit marked the outline `REVISE` and identified those omissions before implementation approval.

Correction: Added `page_budget=2`, document name/hash/page citation metadata, `resolve_citations`, and `retrieve_context` fail-fast dispatch behavior with focused tests.

Evidence: `scripts/retrieval.py`, `tests/test_retrieval.py`, `RAG_PIPELINE_PLAN.md:255-267`; `.venv/bin/python -m pytest -q` → 15 passed.

`/status` model and token use: unavailable in this API session.

Preventive rule: Review each plan step against both the pipeline requirement and an executable verification assertion before implementation.

### C007: Parallel Wave 1 preflight implementation

Date: 2026-08-16
Participants: Human, Codex, three parallel implementation workers
Type: Agent correction and blocker
Related commit: pending
`/status` model and token use: unavailable in this API session.

Context: The human requested parallel implementation of T04, T05, and T06. The three lanes were assigned disjoint files and reviewed by the integration owner.

What was learned: T04 was fully reproducible and passed a temporary Python 3.12.7 install of all 56 locked packages. T05 and T06 required external state unavailable to this environment: Ollama was not reachable and the `datasets` package was not available to the execution interpreter.

How it was caught: Focused tests passed (13 total), but the preflight commands returned blocked status with null identity/hash fields. The full suite remained at 31 passed and three pre-existing migration failures in `test_verify_eval.py`; those failures were not changed because they are outside T04–T06 scope.

Correction: Added bounded rerunnable tooling and preserved explicit blocked artifacts rather than fabricating model digests, downloaded-file hashes, row counts, or smoke results. C01 remains blocked until the host provides Ollama and the pinned dataset tooling/cache.

Evidence: `scripts/lock_install.py`, `artifacts/lock.v1.json`, `scripts/preflight_ollama.py`, `artifacts/ollama_preflight.v1.json`, `scripts/materialize_dataset.py`, `artifacts/dataset_materialization.v1.json`, and `TASKS.md` T04–T06.

Preventive rule: External preflight tasks may be implemented in parallel, but their completion checkboxes stay open until the captured identity and materialization evidence actually exists.

### C008: Ollama digest-format correction

Date: 2026-08-16
Participants: Human, Codex
Type: Agent correction
Related commit: pending
`/status` model and token use: unavailable in this API session.

Context: The Ollama host returned version `0.32.13`, a successful `qwen3:4b` pull, and digest `359d7dd4...74fae7` from `/api/tags`.

What was wrong: The preflight accepted only a digest prefixed with `sha256:`, while Ollama returned the valid digest as bare 64-character hexadecimal text. The original test fixture also used invalid `sha256:abc` data.

Correction: Normalize valid bare or prefixed SHA-256 values to lowercase `sha256:<digest>` and use a real 64-hex fixture. The host artifact remains blocked until the corrected script is rerun because this environment cannot access the host’s Ollama service.

Evidence: `scripts/preflight_ollama.py`, `tests/test_ollama_preflight.py`, user-provided `/api/tags` output, and focused test result `7 passed`.

Preventive rule: Validate external API identity formats against observed provider output and use structurally valid fixtures, not abbreviated placeholders.

## Entry template

```markdown
### CXXX: Short decision or correction title

Date:
Participants:
Type: Human direction | Human approval | Agent proposal | Agent correction | Rejected approach
Related commit (if applicable)
`/status` model and token use (for all commits):

Context:

Human direction or decision:

Agent contribution:

What was wrong or uncertain:

How it was caught:

Correction or final decision:

Evidence:

Preventive rule or learning:

Follow-up:
```

## 2026-08-16 — feasibility and ingestion foundation

- Context: items 4 and 5 requested from `TASKS.md`.
- Changed: added offline feasibility probes and deterministic PyMuPDF page ingestion with content-addressed evidence IDs; added focused tests and README command documentation.
- Learning: the system Python was not the pinned environment, and sandboxed `sysctl` can fail even when present. Validation therefore uses `.venv/bin/python`, while the probe records unavailable memory telemetry as an explicit failed capability. `/status` was unavailable in this session, so no token/model record was added.

## 2026-08-16 — M03 approval and M05 gate attempt

- Context: user approved M03 and requested M05 execution.
- Evidence: environment manifest validation passed; the offline feasibility probe passed text, swap-command, prefix-hash, and runtime-configuration checks. `vllm`, `mlx`, and `mlx_vlm` were absent, `runtime.server_revision` was unset, and sandboxed `sysctl` memory telemetry failed.
- Decision: M03 is complete. M05 remains blocked because real multimodal smoke, image identity, OOM/CPU-fallback/swap, and prefix-cache checks require the target runtime and hardware environment.

## 2026-08-16 — vLLM-Metal runtime installed

- Context: user requested package installation to continue M05.
- Evidence: official installer created `/Users/dmondal/.venv-vllm-metal` with vLLM `0.27.1+cpu`, vLLM-Metal `0.3.0.dev20260815085651`, MLX `0.32.0`, and MLX-VLM `0.6.4`; native architecture is `arm64`.
- Blocker: `vllm --version` terminated with `No Metal device available`, so the sandbox cannot run the GPU-backed smoke test. Exact installed versions were recorded in `environment/manifest.v1.json`; M05 remains blocked pending a Metal-accessible run.

## 2026-08-16 — bounded runtime smoke script

- Context: target MLX reported `Device(gpu, 0)` and the user requested implementation of the remaining M05 runner.
- Changed: added `scripts/run_runtime_smoke.py`, which launches only its own OpenAI-compatible vLLM server, bounds startup and request time, exercises text and image requests, captures server-log failure evidence, and cleans up the child process.
- Next step: run it on the Metal-accessible M4 Pro and inspect `artifacts/runtime_smoke.v1.json` before declaring M05 passed.

## 2026-08-16 — M05 smoke result and memory target correction

- Evidence: `runtime_smoke.v4.json` passed health, text, and image requests; observed peak memory was 17.08 GB.
- Decision: User confirmed 24 GB available memory, so `environment/manifest.v1.json` now records `unified_memory_gib: 24`. M05 remains open pending swap/OOM, CPU-fallback, prefix-cache, and repeatability checks; the detailed checklist is recorded in `PROGRESS.md`.

## 2026-08-16 — M05 plan review

- Review: applied the `review-plan` skill against the assignment and `RAG_PIPELINE_PLAN.md`.
- Verdict: REVISE. The original checklist had the right risk areas but lacked per-condition JSON evidence, explicit pass/fail gates, cache controls, and a non-ambiguous image fixture.
- Correction: `PROGRESS.md` now specifies the evidence schema and acceptance conditions for memory/swap, CPU fallback, prefix-cache parity, concurrency, and image validation. The approved plan now reflects the confirmed 24 GB target.

## 2026-08-16 — automated M05 evidence runner

- Context: the user approved implementation after reviewing the M05 plan and the practical impact of the memory safety margin.
- Decision: use a 4 GiB safety margin on the 24 GiB M4 Pro target, making 20 GiB the observed server-RSS qualification ceiling. This protects the machine from likely memory pressure; it is not a reserved allocation.
- Changed: added a bounded runner for the memory-fraction sweep, GPU/Metal log checks, cache parity and image identity, fresh/warm requests, and concurrency 2/4. It preserves one JSON record per condition and an aggregate result, including failures.
- Evidence: `.venv/bin/python -m pytest -q` → 20 passed; `.venv/bin/python scripts/run_m05_feasibility.py --help` succeeded. The system Python lacks PyMuPDF, so validation must use the pinned `.venv`.
- `/status` model and token use: unavailable in this API session.

## 2026-08-16 — M05 memory-sweep aggregation correction

- Context: final review of the automated M05 result aggregation.
- Correction: a failed exploratory higher memory fraction is retained as evidence but does not fail M05 when a lower fraction passes and is selected. The final gate still requires the selected fraction plus cache and concurrency conditions to pass.
- Evidence: focused acceptance test and the full `.venv/bin/python -m pytest -q` suite.
- `/status` model and token use: unavailable in this API session.

## 2026-08-16 — text-RAG package layout finalized

- Context: completed the T09a package-layout cleanup after ingestion and retrieval moved into dedicated packages.
- Decision: keep `scripts.ingestion` and `scripts.retrieval` as the only supported text-RAG entrypoints, retain `scripts.legacy.retrieval` unchanged for legacy behavior, and remove all retired top-level wrapper paths from validation-facing docs and tests.
- Evidence: `tests/retrieval/test_cli.py`, `docs/superpowers/plans/2026-08-16-text-rag-package-layout.md`, and the T09a validation commands.
- `/status` model and token use: unavailable in this API session.

## 2026-08-16 — Retire stale multimodal verifier tests

- Context: the completed package-refactor branch retained three unrelated full-suite failures from tests that asserted the superseded multimodal runtime and fixtures.
- Decision: user explicitly approved deletion of `tests/test_verify_eval.py`; its GitNexus impact analysis found no callers or affected execution flows.
- Evidence: the removed assertions expected vLLM-Metal, a multimodal schema title, and non-empty retired fixtures, all contrary to the approved text-RAG plan.
- `/status` model and token use: unavailable in this API session.

## 2026-08-16 — Qwen3 model-tag correction and swap gate

- Context: `qwen3:4b` ignored `think=false`; the user identified the separate non-thinking `qwen3:4b-instruct` tag.
- Changed: pinned the instruct tag throughout the current model contract and added bounded 250 ms macOS `vm.swapusage` sampling to the Ollama preflight. Consecutive nonzero samples now fail the preflight.
- Evidence: focused preflight tests passed (`10 passed`); the host preflight returned `READY` for buffered and streaming responses with digest `sha256:0edcdef...f168ba0`, but recorded sustained swap peaking at 1,202,129,469 bytes and therefore failed truthfully.
- Learning: a passing model response is insufficient for a latency benchmark gate when memory pressure persists; resource qualification must be part of the preflight predicate.
- `/status` model and token use: unavailable in this API session.

## 2026-08-16 — Ollama preflight cleared after memory reset

- Evidence: regenerated `artifacts/ollama_preflight.v1.json` passed with `qwen3:4b-instruct`, digest `sha256:0edcdef...f168ba0`, buffered/streaming final-text parity, and nine 250 ms swap samples with a zero-byte maximum.
- Decision: T05 is complete; C01 remains blocked only by T06 dataset materialization.
- `/status` model and token use: unavailable in this API session.

## 2026-08-16 — Dataset materialization cleared C01

- Evidence: `datasets==5.0.1` in the project environment materialized the pinned corpus (3,200 passages) and QA split (918 rows); both downloaded-file and normalized-corpus hashes are recorded in `artifacts/dataset_materialization.v1.json`.
- Decision: T06 and C01 are complete. The next dependency is T07's manual QA-to-passage verification, not further runtime setup.
- `/status` model and token use: unavailable in this API session.

## 2026-08-16 — Offline text-corpus ingestion boundary

- Context: implementing the approved text-RAG ingestion and BM25 retrieval foundation.
- Correction: direct `load_dataset` ingestion retried Hub metadata checks even with a local-only download configuration in `datasets==5.0.1`. The ingestion CLI now reads the uniquely pinned cached Arrow file directly, so no network is part of the ingestion path.
- Evidence: focused tests cover cache-only Arrow discovery, content-addressed manifest construction, deterministic BM25 ranking, bounded `SOURCE_N` context admission, and both direct CLIs. The real cached corpus produced 3,200 passages, corpus hash `dbe884c2...0aa728d`, and index snapshot `b4942595...81c6c7`.
- Learning: a downloader's `local_files_only` flag does not necessarily prevent metadata resolution during builder construction; use a local artifact reader when the measurement contract requires an offline boundary.
- `/status` model and token use: unavailable in this API session.

## 2026-08-16 — Text-RAG package ownership

- Context: user requested a cleaner repository layout after the ingestion/retrieval foundation was completed.
- Decision: move every new text-RAG command and module into `scripts.ingestion` or `scripts.retrieval`, mirror that split in tests, and deliberately remove top-level compatibility wrappers.
- Reasoning: the split follows the durable-corpus versus query-time boundary and prevents the current generic `text_rag.py` module from becoming a mixed-responsibility home.
- `/status` model and token use: unavailable in this API session.
