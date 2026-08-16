# Text-RAG Package Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every text-RAG ingestion and retrieval module, command, and focused test into ownership-aligned packages without changing observable behavior.

**Architecture:** `scripts.ingestion` owns pinned data materialization, offline Arrow reading, normalization, and text-evidence manifests. `scripts.retrieval` owns manifest parsing, deterministic BM25 ranking, bounded context assembly, and the query command. The old top-level text-RAG paths are removed; callers use module execution exclusively.

**Tech Stack:** Python 3.12, Hugging Face Datasets Arrow reader, rank-bm25, pytest, JSON.

## Global Constraints

- Preserve the pinned `rag-datasets/rag-mini-wikipedia` revision and the offline Arrow-cache ingestion boundary.
- Preserve text-evidence manifest schema `text-evidence-manifest.v1`, durable `passage:<id>` evidence IDs, SHA-256 hashes, and deterministic index snapshots.
- Preserve the frozen BM25 parameters `k1=1.2`, `b=0.75`, retrieval default `retrieve_k=20`, context default `admitted_top_k=5`, and character budget `12_000`.
- Do not recreate the retired top-level ingestion or retrieval wrappers; use package entrypoints only.
- Move the legacy PDF/multimodal `scripts/retrieval.py` module unchanged to `scripts/legacy/retrieval.py`, with its matching tests and imports, to free the `scripts.retrieval` package name. Leave every other legacy PDF/multimodal script and test unchanged.
- Run module commands with `python -m scripts.ingestion.run` and `python -m scripts.retrieval.run`.

---

### Task 1: Move ingestion ownership into `scripts.ingestion`

**Files:**
- Create: `scripts/ingestion/__init__.py`
- Create: `scripts/ingestion/materialize.py`
- Create: `scripts/ingestion/corpus.py`
- Create: `scripts/ingestion/run.py`
- Modify: `tests/test_dataset_materialization.py` → `tests/ingestion/test_materialize.py`
- Create: `tests/ingestion/test_corpus.py`
- Modify: `tests/test_text_rag.py` (remove only the ingestion-specific cases)
- Delete: `scripts/materialize_dataset.py`
- Delete: the retired top-level ingestion wrapper

**Interfaces:**
- Consumes: cached `rag-mini-wikipedia-passages.arrow` and `artifacts/dataset_materialization.v1.json`.
- Produces: `materialize(cache_root, loader, repo_root) -> dict[str, Any]`; `ingest_passages(rows, corpus_hash) -> dict[str, Any]`; `load_cached_passages(cache_root, revision, dataset_from_file) -> tuple[dict[str, Any], ...]`; `python -m scripts.ingestion.run`.

- [ ] **Step 1: Extract only the ingestion tests into a new failing package test file**

```python
from scripts.ingestion.corpus import ingest_passages, load_cached_passages
from scripts.ingestion.materialize import materialize

result = subprocess.run([sys.executable, "-m", "scripts.ingestion.run", "--help"], ...)
assert result.returncode == 0
```

- [ ] **Step 2: Run tests to verify the new package imports fail**

Run: `.venv/bin/python -m pytest tests/ingestion/test_materialize.py tests/ingestion/test_corpus.py -q`

Expected: FAIL because `scripts.ingestion` does not yet exist.

- [ ] **Step 3: Extract the materialization module unchanged**

Move `DATASET_REPOSITORY`, `DATASET_REVISION`, `LoadedRows`, `MaterializationError`, normalization/hash helpers, `load_huggingface`, `materialize`, and `write_manifest` into `scripts/ingestion/materialize.py`. Preserve the existing `local_files_only` argument and its `DownloadConfig` behavior. Move the existing materialization test file intact to `tests/ingestion/test_materialize.py`.

- [ ] **Step 4: Extract corpus ingestion and the module CLI**

Move `TextRagError`, `normalize_text`, SHA-256/canonical-json helpers, `Passage`, `ingest_passages`, and `load_cached_passages` into `scripts/ingestion/corpus.py`. Move only the three ingestion cases from `tests/test_text_rag.py` into `tests/ingestion/test_corpus.py`: manifest construction, malformed passages, and cached Arrow discovery. Move the existing `ingest_from_materialization`, JSON writer, argument parsing, and error-to-exit-code behavior into `scripts/ingestion/run.py`, importing only from its sibling modules.

- [ ] **Step 5: Run the ingestion tests and the real offline command**

Run:

```bash
.venv/bin/python -m pytest tests/ingestion/test_materialize.py tests/ingestion/test_corpus.py -q
.venv/bin/python -m scripts.ingestion.run --cache-root /private/tmp/t06-dataset-cache --output artifacts/text_evidence_manifest.v1.json
```

Expected: all focused tests pass and the command reports 3,200 ingested passages without network requests.

- [ ] **Step 6: Commit**

```bash
git add scripts/ingestion tests/ingestion artifacts/text_evidence_manifest.v1.json
git commit -m "refactor(ingestion): group text corpus modules"
```

### Task 2: Move retrieval ownership into `scripts.retrieval`

**Files:**
- Create: `scripts/retrieval/__init__.py`
- Create: `scripts/retrieval/bm25.py`
- Create: `scripts/retrieval/context.py`
- Create: `scripts/retrieval/run.py`
- Create: `scripts/legacy/__init__.py`
- Move: `scripts/retrieval.py` → `scripts/legacy/retrieval.py`
- Move: `tests/test_retrieval.py` → `tests/legacy/test_retrieval.py`
- Modify: remaining `tests/test_text_rag.py` → `tests/retrieval/test_bm25.py`, `tests/retrieval/test_context.py`, and `tests/retrieval/test_cli.py`
- Delete: the retired top-level retrieval wrapper
- Delete: the retired top-level text-RAG wrapper

**Interfaces:**
- Consumes: `text-evidence-manifest.v1` manifests.
- Produces: `build_index(manifest) -> BM25Index`; `retrieve(index, query, retrieve_k=20) -> tuple[RetrievedPassage, ...]`; `assemble_context(ranked, admitted_top_k=5, character_budget=12_000) -> AssembledContext`; `python -m scripts.retrieval.run`.

- [ ] **Step 1: Split the current retrieval tests by public interface**

```python
from scripts.retrieval.bm25 import build_index, retrieve
from scripts.retrieval.context import assemble_context

result = subprocess.run([sys.executable, "-m", "scripts.retrieval.run", "--manifest", str(path), "--question", "..."], ...)
assert json.loads(result.stdout)["admitted_evidence_ids"] == ["passage:2", "passage:7"]
```

- [ ] **Step 2: Run tests to verify imports fail before extraction**

Run: `.venv/bin/python -m pytest tests/retrieval -q`

Expected: FAIL because `scripts.retrieval` does not yet exist.

- [ ] **Step 3: Extract deterministic BM25 mechanics**

Move the evidence-manifest version, BM25 constants, tokenization, canonical snapshot checks, `Passage`, `RetrievedPassage`, `BM25Index`, `build_index`, and `retrieve` to `scripts/retrieval/bm25.py`. Keep validation errors as a retrieval-local `RetrievalError` so the retrieval package does not depend on ingestion implementation.

- [ ] **Step 4: Extract context packing and citations**

Move `AssembledContext` and `assemble_context` into `scripts/retrieval/context.py`. Import `RetrievedPassage` from `.bm25`; preserve rank order, `SOURCE_N [passage:id]` formatting, character-budget behavior, and `zero_admissible_evidence` abstention.

- [ ] **Step 5: Move the retrieval command**

Move manifest loading, argument parsing, JSON output, and `RetrievalError` handling into `scripts/retrieval/run.py`. It must load only the durable manifest and emit ranked IDs/scores, admitted IDs, context, abstention state, reason, and input-character count.

- [ ] **Step 6: Run focused retrieval checks and the real manifest command**

Run:

```bash
.venv/bin/python -m pytest tests/retrieval -q
.venv/bin/python -m scripts.retrieval.run --manifest artifacts/text_evidence_manifest.v1.json --question "What city is the capital of France?" --admitted-top-k 2 --character-budget 2000
```

Expected: focused tests pass; the command returns JSON with ranked and admitted durable evidence IDs.

- [ ] **Step 7: Commit**

```bash
git add scripts/retrieval tests/retrieval
git commit -m "refactor(retrieval): group BM25 context modules"
```

### Task 3: Remove old paths and update repository references

**Files:**
- Delete: `tests/test_text_rag.py`
- Delete: any now-empty top-level text-RAG files listed in Tasks 1–2
- Modify: `TASKS.md`
- Modify: `COLLABORATION_NOTES.md`

**Interfaces:**
- Consumes: completed ingestion and retrieval package commands.
- Produces: only the new module paths in code, tests, task tracking, and generated evidence commands.

- [ ] **Step 1: Write a negative path test for removed commands**

```python
for path in retired_paths:
    assert not path.exists()
```

- [ ] **Step 2: Remove the retired text-RAG paths and update references**

Delete only the three top-level text-RAG files and their consolidated test after imports/tests are relocated. Mark `T09a` complete and record the moved command paths in the concise collaboration log.

- [ ] **Step 3: Run scope, test, and command validation**

Run:

```bash
rg -n "scripts\.(ingest_corpus|retrieve|text_rag)|scripts/(ingest_corpus|retrieve|text_rag)\.py" scripts tests README.md ARCHITECTURE.md RAG_PIPELINE_PLAN.md TASKS.md
.venv/bin/python -m pytest tests/ingestion tests/retrieval -q
git diff --check
```

Expected: no references to retired text-RAG paths, all focused tests pass, and no whitespace errors.

- [ ] **Step 4: Run final impact analysis and commit**

Run GitNexus `detect_changes()` and verify only the expected ingestion/retrieval modules and tests are affected. Then:

```bash
git add scripts tests TASKS.md COLLABORATION_NOTES.md
git commit -m "refactor(rag): retire top-level text pipeline paths"
```

## Plan Review

- Coverage: Tasks 1 and 2 cover every approved ownership boundary and command. Task 3 enforces the explicit no-wrapper requirement and records completion.
- No placeholders: the plan defines exact paths, names, command forms, failure assertions, and validation commands.
- Type consistency: ingestion produces the unchanged text-evidence manifest consumed by retrieval; retrieval’s `RetrievedPassage` is the only input to context packing.
