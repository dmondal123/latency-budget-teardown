# Text-RAG Evaluation Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and verify an auditable seeded 30-case text-RAG suite for T07 and T08.

**Architecture:** A deterministic candidate generator produces a review ledger from the pinned local Arrow splits. Only reviewed evidence mappings become fixtures; a text-RAG verifier checks the fixtures against the pinned corpus and dataset manifest.

**Tech Stack:** Python 3.12, PyArrow, JSON Schema, pytest, JSON.

## Global Constraints

- Preserve the frozen `20260816` seed, pinned dataset revision, and 8/8/7/7 allocation.
- Use test-first changes and record the observed failing test before production implementation.
- Do not claim human G1 approval or inspect model outputs.
- Keep unrelated user modifications to `AGENTS.md` and `CLAUDE.md` untouched.

---

### Task 1: Review-ledger preparation

**Files:**

- Modify: `scripts/prepare_eval.py`
- Modify: `tests/test_eval_preparation.py`

**Interfaces:**

- Produces candidate and reviewed-mapping records containing `source_row_id`, `answer_type`, `candidate_passage_ids`, `gold_evidence_ids`, `support_quote`, `review_method`, and `verification_status`.

- [ ] Write a failing focused test that rejects an unreviewed or quote-less mapping.
- [ ] Run `pytest tests/test_eval_preparation.py -q` and confirm the new assertion fails for the expected missing validation.
- [ ] Implement the smallest review-record validation and deterministic bounded selection needed by the test.
- [ ] Re-run `pytest tests/test_eval_preparation.py -q` and confirm it passes.

### Task 2: Text-RAG verifier and contract alignment

**Files:**

- Modify: `scripts/verify_eval.py`
- Create: `tests/test_verify_eval.py`
- Modify: `contracts/behavioral_contract.v1.json`
- Modify: `contracts/thresholds.2026-08-16.json`

**Interfaces:**

- Consumes the text-RAG case arrays, holdout manifest, dataset manifest, and local Arrow corpus.
- Produces a non-zero exit and a specific diagnostic for invalid identity, quote, split, or manifest data.

- [ ] Write failing verifier tests for a non-exact quote and a mismatched holdout manifest.
- [ ] Run `pytest tests/test_verify_eval.py -q` and confirm the tests fail because the retired verifier validates the wrong schema.
- [ ] Implement only text-RAG validation and align the contract/budget field names it validates.
- [ ] Re-run `pytest tests/test_verify_eval.py -q` and confirm it passes.

### Task 3: Reviewed suite materialization and integration

**Files:**

- Create: `eval/v1/candidate_ledger.json`
- Create: `eval/v1/reviewed_mappings.json`
- Modify: `eval/v1/development_cases.json`
- Modify: `eval/v1/holdout_cases.json`
- Modify: `eval/v1/holdout_manifest.json`
- Modify: `TASKS.md`
- Modify: `PROGRESS.md`

- [ ] Generate and review 30 accepted mappings with exact corpus quotes; retain rejected/ambiguous candidates in the ledger.
- [ ] Materialize only validated records into a deterministic 24/6 split.
- [ ] Run all focused tests and `python scripts/verify_eval.py --repo-root .`.
- [ ] Compare replayed selected source rows and holdout IDs with persisted fixtures.
- [ ] Update T07/T08/C02 state accurately and commit the coherent feature after GitNexus change detection.

## Self-review

- Coverage: each T07/T08 requirement has a materialization step and a test or verifier assertion.
- Scope: no benchmark, model, retrieval, or holdout-answer execution is included.
- Consistency: records use corpus passage IDs, not QA IDs, and retain the frozen answer-type allocation.
