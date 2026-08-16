# Text-RAG Layout Design

## Goal

Separate the approved text-RAG ingestion and retrieval implementation into
clear, independently executable subsystem folders.

## Scope

Move every text-RAG module, executable command, and focused test from the
top-level `scripts/` and `tests/` namespaces into one of these folders:

```text
scripts/
  ingestion/
    __init__.py
    materialize.py
    corpus.py
    run.py
  retrieval/
    __init__.py
    bm25.py
    context.py
    run.py
tests/
  ingestion/
    test_materialize.py
    test_corpus.py
  retrieval/
    test_bm25.py
    test_context.py
    test_cli.py
```

The legacy PDF/multimodal retrieval module moves unchanged to
`scripts/legacy/retrieval.py` with its tests so that its current
`scripts/retrieval.py` filename no longer blocks the text-RAG retrieval
package. Other older PDF/multimodal scripts remain out of scope.

## Architecture

`scripts.ingestion` owns all durable-corpus work. `materialize.py` retains
the pinned Hugging Face dataset materialization helpers; `corpus.py` owns
offline Arrow-cache discovery, normalization, hashing, and evidence-manifest
creation; `run.py` exposes the ingestion command.

`scripts.retrieval` owns only query-time work. `bm25.py` defines the passage
records, deterministic BM25 index, and stable ranks; `context.py` binds
admitted ranked passages to `SOURCE_N` labels under the character budget;
`run.py` exposes the retrieval command.

`scripts.legacy.retrieval` retains the previous PDF/multimodal retrieval API.
Its only changes are the package path and corresponding test imports.

The commands intentionally move to module execution:

```bash
python -m scripts.ingestion.run
python -m scripts.retrieval.run --manifest artifacts/text_evidence_manifest.v1.json --question "..."
```

There are no compatibility wrappers at the old top-level paths. Documentation
and tests will use only the new module paths.

## Data flow

```text
pinned Arrow cache
  → scripts.ingestion.corpus
  → text-evidence manifest + index snapshot
  → scripts.retrieval.bm25
  → scripts.retrieval.context
  → bounded cited context
```

The manifest remains the durable evidence contract. The BM25 index is rebuilt
in memory from it; no embedding or vector database is introduced.

## Error handling

Ingestion rejects missing or ambiguous cached Arrow files, unexpected schema,
invalid hashes, duplicate passage IDs, and empty normalized passages.
Retrieval rejects malformed manifests, snapshot drift, invalid metadata, and
negative budgets. Empty retrieval or fully over-budget admission produces a
deterministic abstention with `zero_admissible_evidence`.

## Testing

Tests mirror the two subsystem boundaries. Ingestion tests cover offline cache
selection, identity binding, normalization, and manifest construction.
Retrieval tests cover stable ranks, snapshot validation, bounded admission,
citation labels, abstention, and each module CLI. Tests must use the new module
commands directly so removed top-level command paths cannot silently persist.
