"""Deterministically propose text-RAG evidence candidates for human review."""

from __future__ import annotations

import random
import re
from typing import Iterable, Mapping

from scripts.materialize_dataset import normalize_text


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
    qa_rows: Iterable[Mapping[str, object]], corpus_rows: Iterable[Mapping[str, object]], *, seed: int
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
            candidates.append({"source_row_id": row["id"], "question": row["question"], "reference_answer": row["answer"], "answer_type": kind, "candidate_passage_ids": matches})
    return candidates
