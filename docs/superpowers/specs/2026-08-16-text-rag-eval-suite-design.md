# Text-RAG Evaluation Suite Design

## Goal

Redo Tasks T07 and T08 with an auditable, deterministic 30-case text-RAG evaluation suite drawn from the pinned local corpus and QA split.

## Scope and constraints

- Use seed `20260816` and the pinned `rag-mini-wikipedia` revision recorded in `eval/v1/dataset_manifest.json`.
- Select exactly 30 distinct QA source rows in the frozen 8 boolean, 8 numeric/date, 7 short-phrase, and 7 free-form allocation.
- Treat QA IDs and corpus passage IDs as distinct identifiers.
- Mark a mapping `manually_verified` only when the review record contains a selected corpus passage, an exact support quote, and a concise rationale.
- Materialize 24 development cases and six sealed holdouts, stratified as 6/6/6/6 development and 2/2/1/1 holdout cases.
- The verifier validates the text-RAG schema, corpus quote containment, suite identity, duplicate prevention, split allocation, and holdout manifest. It must not load or validate retired PDF/multimodal fields.
- The resulting suite remains pending human G1 approval; no benchmark or holdout outputs are run or inspected.

## Design

`scripts.prepare_eval` deterministically orders QA rows by answer type and seed, produces candidate passage IDs by normalized containment, and persists a candidate ledger. Review records are a separate durable input: rejected and ambiguous candidates remain explicit, while only records with evidence and review provenance may enter materialization.

The materializer emits development and holdout JSON arrays plus a manifest containing the suite identity, seed, dataset identity, corpus hash, review method, and holdout case IDs. The fixture verifier loads the local Arrow corpus and dataset manifest, checks every selected ID and quote, validates the 24/6 split and type distributions, and rejects stale/PDF contract terminology.

## Verification

Focused tests prove that unreviewed mappings, fabricated quotes, duplicate source rows, incorrect distributions, corpus identity drift, and malformed manifests fail. The authoritative command is:

```bash
python scripts/verify_eval.py --repo-root .
```

The suite’s acceptance condition is a successful verifier run plus a replay that produces the same selected source rows and holdout IDs from the reviewed ledger.
