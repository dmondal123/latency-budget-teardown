"""Context packing for admitted ranked text evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .bm25 import RetrievedPassage, RetrievalError


@dataclass(frozen=True)
class AssembledContext:
    admitted_evidence_ids: tuple[str, ...]
    text: str
    abstained: bool
    reason: str | None
    input_characters: int


def assemble_context(
    ranked: Sequence[RetrievedPassage], *, admitted_top_k: int = 5, character_budget: int = 12_000
) -> AssembledContext:
    """Pack rank-ordered whole passages, binding labels only after admission."""
    if admitted_top_k < 0 or character_budget < 0:
        raise RetrievalError("context budgets must be non-negative")
    sections: list[str] = []
    evidence_ids: list[str] = []
    for item in ranked:
        if len(evidence_ids) >= admitted_top_k:
            break
        label = f"SOURCE_{len(evidence_ids) + 1}"
        section = f"{label} [{item.evidence_id}]\n{item.text}"
        next_length = sum(len(part) for part in sections) + (2 * len(sections)) + len(section)
        if next_length > character_budget:
            continue
        sections.append(section)
        evidence_ids.append(item.evidence_id)
    if not sections:
        return AssembledContext((), "", True, "zero_admissible_evidence", 0)
    text = "\n\n".join(sections)
    return AssembledContext(tuple(evidence_ids), text, False, None, len(text))
