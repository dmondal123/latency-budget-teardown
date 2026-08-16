"""Validation rejects malformed or out-of-context answers."""

import pytest

from scripts.answer_validation import validate_answer


def test_valid_answer_resolves_only_admitted_source_labels():
    result = validate_answer('{"answer":"Paris","abstained":false,"citations":["SOURCE_1"]}', {"SOURCE_1": 42})
    assert result.valid is True
    assert result.citation_ids == (42,)


def test_unadmitted_citation_and_unfounded_answer_are_fatal():
    citation = validate_answer('{"answer":"Paris","abstained":false,"citations":["SOURCE_2"]}', {"SOURCE_1": 42})
    empty = validate_answer('{"answer":"Paris","abstained":false,"citations":[]}', {})
    assert citation.fatal_gates == ("citation_outside_admitted_context",)
    assert empty.fatal_gates == ("non_abstaining_answer_with_no_admissible_evidence",)
