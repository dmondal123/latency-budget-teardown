"""Deterministic validation for the small model-answer JSON contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

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
    if not isinstance(answer, dict):
        return ValidationResult(False, (), ("malformed_output_or_citation_schema",))
    answer_text = answer.get("answer")
    if isinstance(answer_text, bool):
    # A yes/no question answered with a JSON boolean (true/false) is a
    # well-formed answer, not a schema violation. Normalise it to Yes/No so
    # downstream grading treats it as the correct polarity.
        answer_text = "Yes" if answer_text else "No"
        answer = {**answer, "answer": answer_text}
    if not isinstance(answer_text, str) or not isinstance(answer.get("abstained"), bool) or not isinstance(answer.get("citations"), list):
        return ValidationResult(False, (), ("malformed_output_or_citation_schema",))
    if "<think>" in raw.casefold() or "thinking" in answer or "thoughts" in answer:
        return ValidationResult(False, (), ("thinking_mode_enabled",))
    if answer["abstained"]:
        return ValidationResult(True, (), ())
    if not bindings:
        return ValidationResult(False, (), ("non_abstaining_answer_with_no_admissible_evidence",))
    if not all(isinstance(citation, str) for citation in answer["citations"]):
        return ValidationResult(False, (), ("malformed_output_or_citation_schema",))
    if any(citation not in bindings for citation in answer["citations"]):
        return ValidationResult(False, (), ("citation_outside_admitted_context",))
    return ValidationResult(True, tuple(bindings[citation] for citation in answer["citations"]), ())
