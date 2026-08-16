"""Deterministically propose text-RAG evidence candidates for human review."""

from __future__ import annotations

import random
import re
import json
from collections import Counter
from typing import Iterable, Mapping
from pathlib import Path

from scripts.materialize_dataset import normalize_text


def load_arrow_rows(path: Path) -> list[dict[str, object]]:
    """Read a materialized Arrow split directly, without Hugging Face network access."""
    import pyarrow as pa

    with pa.memory_map(str(path), "r") as source:
        return [dict(row) for row in pa.ipc.open_stream(source).read_all().to_pylist()]


def write_candidate_ledger(path: Path, candidates: Iterable[Mapping[str, object]], *, max_candidates: int = 25) -> None:
    payload = {"schema_version": "text-rag-candidate-ledger.v1", "selection_seed": 20260816,
               "max_candidates": max_candidates, "candidates": [dict(candidate) for candidate in candidates]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def choose_support_mappings(candidates: Iterable[Mapping[str, object]], corpus_rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Propose one answer-bearing sentence per candidate; humans approve it later."""
    passages = {row["id"]: normalize_text(str(row["passage"])) for row in corpus_rows}
    proposals = []
    for candidate in candidates:
        answer = normalize_text(str(candidate["reference_answer"]))
        choices = [(identifier, passages[identifier]) for identifier in candidate["candidate_passage_ids"] if identifier in passages and answer.casefold() in passages[identifier].casefold()]
        if not choices:
            continue
        identifier, passage = min(choices, key=lambda item: (len(item[1]), item[0]))
        sentence = next((part.strip() for part in re.split(r"(?<=[.!?])\s+", passage) if answer.casefold() in part.casefold()), passage)
        proposals.append({**dict(candidate), "gold_evidence_ids": [identifier], "support_quote": sentence, "verification_status": "proposed_manual_review"})
    return proposals


def classify_answer(answer: str) -> str:
    value = normalize_text(answer)
    if value.casefold() in {"yes", "no", "true", "false"}:
        return "boolean"
    if re.fullmatch(r"[0-9][0-9,./:-]*", value):
        return "numeric_or_date"
    if len(value.split()) <= 3:
        return "short_phrase"
    return "free_form"


def select_candidates(
    qa_rows: Iterable[Mapping[str, object]], corpus_rows: Iterable[Mapping[str, object]], *, seed: int, max_candidates: int = 25
) -> list[dict[str, object]]:
    corpus = [(row["id"], normalize_text(str(row["passage"]))) for row in corpus_rows]
    if any(isinstance(identifier, bool) or not isinstance(identifier, int) for identifier, _ in corpus):
        raise ValueError("corpus IDs must be integers")
    ordered = sorted((dict(row) for row in qa_rows), key=lambda row: int(row["id"]))
    groups: dict[str, list[dict[str, object]]] = {kind: [] for kind in ("boolean", "numeric_or_date", "short_phrase", "free_form")}
    for row in ordered:
        groups[classify_answer(str(row["answer"]))].append(row)
    rng = random.Random(seed)
    for rows in groups.values():
        rng.shuffle(rows)
    candidates: list[dict[str, object]] = []
    positions = {kind: 0 for kind in groups}
    while any(positions[kind] < len(rows) for kind, rows in groups.items()):
        for kind, rows in groups.items():
            position = positions[kind]
            if position >= len(rows):
                continue
            row = rows[position]
            positions[kind] += 1
            answer = normalize_text(str(row["answer"])).casefold()
            matches = [identifier for identifier, passage in corpus if answer and answer in passage.casefold()]
            disposition = "pending_manual_review" if matches and len(matches) <= max_candidates else "rejected_ambiguous"
            candidates.append({"source_row_id": row["id"], "question": row["question"], "reference_answer": row["answer"], "answer_type": kind, "candidate_passage_ids": matches, "candidate_count": len(matches), "disposition": disposition})
    return candidates


def materialize_cases(
    approved_rows: Iterable[Mapping[str, object]], *, seed: int, sealed_at: str
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Create a reproducible split only from rows a human has approved."""
    rows = [dict(row) for row in approved_rows]
    if len(rows) != 30:
        raise ValueError("exactly 30 approved mappings are required")
    if len({row.get("source_row_id") for row in rows}) != 30:
        raise ValueError("approved mappings must have unique source row IDs")
    expected = {"boolean": 8, "numeric_or_date": 8, "short_phrase": 7, "free_form": 7}
    grouped = {kind: [] for kind in expected}
    for row in rows:
        kind = row.get("answer_type")
        if kind not in grouped:
            raise ValueError(f"unsupported answer type: {kind}")
        grouped[kind].append(row)
    if Counter({kind: len(group) for kind, group in grouped.items()}) != Counter(expected):
        raise ValueError("approved mappings must use the 8/8/7/7 answer-type allocation")
    holdout_counts = {"boolean": 2, "numeric_or_date": 2, "short_phrase": 1, "free_form": 1}
    rng = random.Random(seed)
    development_rows: list[dict[str, object]] = []
    holdout_rows: list[dict[str, object]] = []
    for kind in expected:
        group = sorted(grouped[kind], key=lambda row: int(row["source_row_id"]))
        rng.shuffle(group)
        holdout_rows.extend(group[:holdout_counts[kind]])
        development_rows.extend(group[holdout_counts[kind]:])
    rows = development_rows + holdout_rows
    development: list[dict[str, object]] = []
    holdouts: list[dict[str, object]] = []
    for ordinal, row in enumerate(rows, 1):
        case = {
            "case_id": f"eval-v1-{ordinal:02d}", "source_row_id": row["source_row_id"],
            "question": row["question"], "reference_answer": row["reference_answer"],
            "answer_type": row["answer_type"], "gold_evidence_ids": row["gold_evidence_ids"],
            "support_quote": row["support_quote"], "expected_abstention": False,
            "verification_status": "manually_verified", "holdout": False,
        }
        target = holdouts if row in holdout_rows else development
        case["holdout"] = target is holdouts
        target.append(case)
    manifest = {"suite_id": "text-rag-latency-eval/v1", "status": "sealed", "selection_seed": seed,
                "sealed_at": sealed_at, "case_ids": [case["case_id"] for case in holdouts]}
    return development, holdouts, manifest
