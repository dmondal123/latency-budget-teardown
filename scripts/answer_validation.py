"""Deterministic validation for the small model-answer JSON contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

from scripts.retrieval import resolve_citations


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    citation_ids: tuple[int, ...]
    fatal_gates: tuple[str, ...]


def validate_answer(raw: str, bindings: Mapping[str, int]) -> ValidationResult:
    try:
        answer = json.loads(raw)
    except json.JSONDecodeError:
        return ValidationResult(False, (), ("malformed_output_or_citation_schema",))
    if not isinstance(answer, dict) or not isinstance(answer.get("answer"), str) or not isinstance(answer.get("abstained"), bool) or not isinstance(answer.get("citations"), list):
        return ValidationResult(False, (), ("malformed_output_or_citation_schema",))
    if "<think>" in raw.casefold() or "thinking" in answer or "thoughts" in answer:
        return ValidationResult(False, (), ("thinking_mode_enabled",))
    if answer["abstained"]:
        return ValidationResult(True, (), ())
    if not bindings:
        return ValidationResult(False, (), ("non_abstaining_answer_with_no_admissible_evidence",))
    if not all(isinstance(citation, str) for citation in answer["citations"]):
        return ValidationResult(False, (), ("malformed_output_or_citation_schema",))
    try:
        citations = resolve_citations(answer["citations"], bindings)
    except ValueError:
        return ValidationResult(False, (), ("citation_outside_admitted_context",))
    return ValidationResult(True, citations, ())
