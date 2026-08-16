from __future__ import annotations

import pytest

from scripts.benchmark import BenchmarkError, select_warmups, validate_conditions


def _case(case_id: str, answer_type: str, *, holdout: bool = False) -> dict[str, object]:
    return {"case_id": case_id, "answer_type": answer_type, "holdout": holdout}


def test_warmups_are_seeded_and_span_answer_types():
    cases = [
        _case(f"{answer_type}-{number}", answer_type)
        for answer_type in ("boolean", "numeric_or_date", "short_phrase", "free_form")
        for number in range(6)
    ]

    warmups = select_warmups(cases, seed=20260816)

    assert len(warmups) == 6
    assert {case["answer_type"] for case in warmups} == {
        "boolean", "numeric_or_date", "short_phrase", "free_form"
    }
    assert all(case["holdout"] is False for case in warmups)
    assert warmups == select_warmups(cases, seed=20260816)


def test_conditions_must_match_the_frozen_order():
    assert validate_conditions("B0_buffered_256,I1_streaming_256,I2_buffered_128") == (
        "B0_buffered_256", "I1_streaming_256", "I2_buffered_128"
    )
    with pytest.raises(BenchmarkError, match="exact"):
        validate_conditions("I1_streaming_256,B0_buffered_256,I2_buffered_128")
