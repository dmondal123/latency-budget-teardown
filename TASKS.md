# Tasks and Ten-Hour Execution Schedule

## Execution labels

- **SEQ:** Critical-path work that starts only after all dependencies pass.
- **PAR-A, PAR-B, PAR-C:** Independent lanes that may run concurrently. Tasks within one lane remain sequential, and each lane owns disjoint files.
- **SERIAL-MEASURE:** Exclusive use of Ollama and the target M4 Pro. Never run two authoritative benchmark jobs concurrently.
- **GATE:** Evidence checkpoint. Downstream work cannot start until it passes.

Use at most three implementation lanes plus one integration owner. The integration owner alone edits shared contracts, configuration, task tracking, and final reports. Parallel workers must not share a test file or modify the same symbol.

## Completed planning

- [x] Reformat the OCR-scanned `TASKS.md` and `RAG_PIPELINE_PLAN.md`, removing accidental duplicate fragments while preserving meaning.
- [x] Reformat the OCR-scanned `ARCHITECTURE.md`, `CONTEXT.md`, and `PROGRESS.md`, preserving meaning and Markdown structure.
- [x] Migrate the environment manifest from the retired multimodal runtime to the approved text-RAG dataset and Ollama contract.
- [x] Align the README with the approved text-RAG/Ollama scope, current G1 status, and available foundation commands.
- [x] Retire the superseded multimodal evaluation fixtures and reset the text-RAG development/holdout fixtures pending verified mappings.
- [x] Migrate the draft behavioral contract to text-RAG evidence, Ollama identity, and text-answer quality fields.
- [x] **T01 [SEQ]** Approve the text-only Hugging Face/Ollama scope and ten-hour design.
- [x] **T02 [SEQ; depends: T01]** Pin the Hugging Face dataset repository and immutable revision.
- [x] **T03 [SEQ; depends: T02]** Rewrite the implementation plan and surrounding architecture/contracts.

## Wave 1 — Preflight and external artifacts (0:00–0:45)

These three lanes start together.

- [x] **T04 [PAR-A; 0:00–0:30; depends: T03]** Lock installs under Python 3.12. Regenerate `requirements.txt` from `requirements.in`; prove the lock is installable. Evidence: `artifacts/lock.v1.json`.
- [x] **T05 [PAR-B; 0:00–0:45; depends: T03]** Pulled `qwen3:4b-instruct`; captured Ollama `0.32.13` and digest `sha256:0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`; buffered/streaming smoke passed with thinking disabled and zero sustained swap. Evidence: `artifacts/ollama_preflight.v1.json`.
- [x] **T06 [PAR-C; 0:00–0:45; depends: T02]** Materialized `text-corpus/passages` (3,200 rows; normalized SHA-256 `dbe884c2...0aa728d`) and `question-answer/test` (918 rows; normalized SHA-256 `ba2cdffb...5569a38`) at the pinned revision. Evidence: `artifacts/dataset_materialization.v1.json`.
- [x] **C01 [GATE; at 0:45; depends: T04, T05, T06]** Confirmed installable lock, expected dataset schemas, immutable model/runtime identity, valid NDJSON streaming, and no sustained swap.

Checkpoint action: if `C01` fails, stop the ten-hour run and record the blocker. Do not silently change the dataset, runtime, model tag, digest, or thinking mode.

## Wave 2 — Evidence and pipeline foundations (0:45–2:15)

- [x] **T09a [SEQ; depends: T10]** Refactor the completed text-RAG ingestion and retrieval foundation into dedicated `scripts/ingestion` and `scripts/retrieval` packages, with mirrored focused tests and no legacy command wrappers.

Dataset evaluation and retrieval implementation run in parallel after `C01`.

- [x] **T07 [PAR-C; 0:45–1:45; depends: C01]** Selected 30 QA rows with seed `20260816`; recorded Codex-assisted manual verification, gold passage IDs, exact support quotes, and review rationale in `eval/v1/candidate_ledger.json` and `eval/v1/reviewed_mappings.json`.
- [x] **T08 [PAR-C; 1:45–2:00; depends: T07]** Materialized 24 development and six sealed holdout cases; the authoritative text-RAG verifier passed against the pinned corpus.
- [x] **T09 [PAR-A; 0:45–1:30; depends: C01]** Implement deterministic passage normalization, BM25 indexing, retrieval, hashes, and focused retrieval tests.
- [x] **T10 [PAR-A; 1:30–2:15; depends: T09]** Implement bounded context assembly and stable `SOURCE N` citation binding with focused tests.
- [x] **T09b [SEQ; depends: T09a]** Remove the stale multimodal verifier tests that conflict with the approved text-RAG fixtures and runtime contract.
- [x] **T11 [PAR-B; 0:45–2:15; depends: C01]** Implement the Ollama NDJSON client, buffered/streamed display, validation, abstention, timeout/error handling, and focused tests.
- [x] **T11a [SEQ; depends: T09a]** Selectively integrate the Wave 2 Ollama client, deterministic answer validation, and offline evaluation-preparation tooling without importing its competing retriever or unverified fixture data.
- [x] **C02 [GATE; at 2:00; depends: T08, T09]** Confirmed 30 verified mappings, sealed 24/6 split, reproducible corpus/index hashes, and working BM25 retrieval.
- [x] **G1 [human approval]** Approved the verified text-RAG case suite, frozen behavioral contract, and provisional latency/quality thresholds before baseline work.

Checkpoint action: if `C02` fails, do not fabricate evidence or unseal holdouts. Drop optional diagnostics and escalate the missing mapping/index evidence immediately.

## Wave 3 — Instrumentation and integration (2:00–5:30)

After each component's interface is stable, instrumentation and independent contract/report fixtures may proceed in parallel. Integration remains sequential.

- [x] **T12 [PAR-A; 2:15–3:30; depends: T10]** Implement stage spans, TTFE/TTFT/first-token-displayed/TTC clocks, telemetry, and raw JSONL persistence with arithmetic tests.
- [x] **T13 [PAR-C; 2:00–3:30; depends: T08]** Add contract, dataset-selection, grading, bootstrap, aligned-waterfall, and tail-analysis fixture tests in disjoint test files.
- [x] **T14 [SEQ; 3:30–4:30; depends: T11, T12, T13]** Integrate the retrieval trace; pass one buffered and one streamed end-to-end fixture, including Ollama validation.
- [ ] **C03 [GATE; at 4:30; depends: T14]** Confirm a complete raw trace, additive TTC arithmetic, citation resolution, thinking disabled, and deterministic final-text parity.
- [ ] **T15 [SEQ; 4:30–5:30; depends: C03]** Implement the condition runner, single-delta assertions, report generation, and fixed-JSONL regression tests.
- [ ] **C04 [GATE; at 5:30; depends: T15]** Confirm the runner can interleave all conditions and regenerate correct fixture waterfalls and marginal tables.

Checkpoint action: authoritative measurement cannot begin without both `C03` and `C04`. If either fails, spend the remaining window producing a verified partial implementation and blocker report rather than untrustworthy benchmark numbers.

## Wave 4 — Authoritative measurements (5:30–7:30)

No implementation lane may run Ollama load, benchmark, or profiling work during this wave. Documentation-only work may continue if it does not change measured source/configuration or create material host load.

- [ ] **T16 [SERIAL-MEASURE; 5:30–7:30; depends: C04, human G1 approval]** Run the seeded, interleaved `B0_buffered_256`, `I1_streaming_256`, and `I2_buffered_128` matrix: 24 development cases × three conditions × five repetitions.
- [ ] **C05 [GATE; at 7:30; depends: T16]** Confirm 360 attempted rows, explicit failure denominators, complete identities, no concurrent benchmark process, and no invalid thermal/swap block.

Checkpoint action: if fewer than 360 valid attempts finish, preserve every row and report the actual denominator. Do not retry measured failures or silently extend past the reporting/packaging reserve.

## Wave 5 — Analysis, decisions, and holdout (7:30–9:15)

Analysis and documentation can run concurrently from the immutable raw traces. Only the holdout benchmark remains serial.

- [ ] **T17 [PAR-A; 7:30–8:10; depends: C05]** Generate aligned p50/p95 waterfalls, marginal-stage tables, case-bootstrap intervals, and top-decile analysis.
- [ ] **T18 [PAR-B; 7:30–8:10; depends: C05]** Score Recall@k/MRR, citations, exact match, token F1, resolution, truncation, and answer-type slices.
- [ ] **T19 [PAR-C; 7:30–8:10; depends: C05]** Draft budget variance, spend, environment, collaboration, and intervention evidence from saved manifests/traces.
- [ ] **C06 [GATE; 8:10–8:30; depends: T17, T18, T19, human G2/G3 approval]** Accept or reject each intervention using frozen intervals and quality gates; define `C_accepted` without inspecting holdout outputs.
- [ ] **T20 [SERIAL-MEASURE; 8:30–8:50; depends: C06]** Run `C_accepted` against six sealed holdouts × five repetitions exactly once.
- [ ] **T21 [SEQ; 8:50–9:15; depends: T20]** Generate final quality, budget, cost, environment, and intervention-decision reports including holdout results.
- [ ] **C07 [GATE; at 9:15; depends: T21]** Confirm every reported number/chart maps to raw data and an exact generation command.

Checkpoint action: if `C06` is not complete by 8:30, do not open the holdout. If the holdout run fails environmentally, report the failure without rerunning it.

## Wave 6 — Reproduction and delivery (9:15–10:00)

- [ ] **T22 [PAR-A; 9:15–9:40; depends: C07]** Run `scripts/reproduce.sh` in the cleanest available environment and save its log.
- [ ] **T23 [PAR-B; 9:15–9:40; depends: C07]** Finalize the ≤2-page write-up and collaboration log using only generated evidence.
- [ ] **T24 [PAR-C; 9:15–9:40; depends: C07]** Audit licenses, secrets, caches, model blobs, generated artifacts, dependency pins, and archive-size inputs.
- [ ] **T25 [SEQ; 9:40–10:00; depends: T22, T23, T24]** Build and validate the submission ZIP; perform final requirement and artifact traceability review.
- [ ] **C08 [GATE; at 10:00; depends: T25, human G4 approval]** Confirm a real ZIP under 500 MB uncompressed with README, source, lock, tests, raw/generated evidence, AI log, and final write-up.

Checkpoint action: packaging never waits for optional cache/top-k diagnostics. If a required artifact is missing at 9:40, record it explicitly and prioritize a truthful, reproducible partial submission over fabricated or hand-copied output.

## Parallelism summary

| Time | Parallel lanes | Sequential/exclusive critical path |
|---|---|---|
| 0:00–0:45 | Lock; Ollama preflight; dataset materialization | `C01` |
| 0:45–2:00 | Eval mapping; BM25/context; Ollama client | `C02` |
| 2:00–4:30 | Instrumentation; report/grader fixtures; component tests | End-to-end integration, `C03` |
| 4:30–5:30 | None required | Runner/report integration, `C04` |
| 5:30–7:30 | Documentation only | All authoritative benchmark requests, `C05` |
| 7:30–8:30 | Latency analysis; quality scoring; report drafting | Intervention decision, `C06` |
| 8:30–9:15 | Report preparation after measurement | Holdout once; final report, `C07` |
| 9:15–10:00 | Reproduction; write-up; artifact audit | ZIP integration, `C08` |
