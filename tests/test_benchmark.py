from __future__ import annotations

import json

import pytest

from scripts.benchmark import (
    BenchmarkError,
    HOLDOUT_CASE_COUNT,
    HOLDOUT_EXPECTED_ATTEMPTS,
    HOLDOUT_EXPECTED_PER_CONDITION,
    HOLDOUT_REPETITIONS,
    _raw_fields,
    load_holdout_cases,
    select_warmups,
    validate_c_accepted_conditions,
    validate_conditions,
)
from scripts.evaluation import C_ACCEPTED, C_ACCEPTED_ORDER


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


def test_c_accepted_contains_all_three_registered_conditions():
    assert C_ACCEPTED == frozenset({"B0_buffered_256", "I1_streaming_256", "I2_buffered_128"})
    assert C_ACCEPTED_ORDER == ("B0_buffered_256", "I1_streaming_256", "I2_buffered_128")


def test_validate_c_accepted_conditions_accepts_exact_set_in_order():
    assert validate_c_accepted_conditions("B0_buffered_256,I1_streaming_256,I2_buffered_128") == (
        "B0_buffered_256", "I1_streaming_256", "I2_buffered_128"
    )


def test_validate_c_accepted_conditions_rejects_wrong_order():
    with pytest.raises(BenchmarkError, match="exactly C_accepted"):
        validate_c_accepted_conditions("I1_streaming_256,B0_buffered_256,I2_buffered_128")


def test_validate_c_accepted_conditions_rejects_subset():
    with pytest.raises(BenchmarkError, match="exactly C_accepted"):
        validate_c_accepted_conditions("B0_buffered_256,I2_buffered_128")


def test_validate_c_accepted_conditions_rejects_unknown_condition():
    with pytest.raises(BenchmarkError, match="exactly C_accepted"):
        validate_c_accepted_conditions("B0_buffered_256,I1_streaming_256,I2_buffered_128,I9_fake")


def test_holdout_denominators_match_case_condition_repetition_product():
    assert HOLDOUT_CASE_COUNT == 6
    assert HOLDOUT_REPETITIONS == 5
    assert HOLDOUT_EXPECTED_ATTEMPTS == 90
    assert HOLDOUT_EXPECTED_PER_CONDITION == 30


def _holdout_case(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "source_row_id": 999,
        "question": "test?",
        "reference_answer": "yes",
        "answer_type": "boolean",
        "gold_evidence_ids": [1],
        "support_quote": "quote",
        "expected_abstention": False,
        "verification_status": "manually_verified",
        "holdout": True,
    }


def _write_cases(path, cases):
    path.write_text(json.dumps(cases), encoding="utf-8")


def test_load_holdout_cases_accepts_six_verified_rows(tmp_path):
    cases = [_holdout_case(f"eval-v1-{i:02d}") for i in range(25, 31)]
    path = tmp_path / "holdout_cases.json"
    _write_cases(path, cases)

    loaded = load_holdout_cases(path)

    assert len(loaded) == 6
    assert all(case["holdout"] is True for case in loaded)


def test_load_holdout_cases_rejects_wrong_count(tmp_path):
    path = tmp_path / "holdout_cases.json"
    _write_cases(path, [_holdout_case(f"eval-v1-{i:02d}") for i in range(25, 28)])

    with pytest.raises(BenchmarkError, match="exactly six"):
        load_holdout_cases(path)


def test_load_holdout_cases_rejects_non_holdout_markings(tmp_path):
    cases = [_holdout_case(f"eval-v1-{i:02d}") for i in range(25, 31)]
    cases[0]["holdout"] = False
    path = tmp_path / "holdout_cases.json"
    _write_cases(path, cases)

    with pytest.raises(BenchmarkError, match="holdout=true"):
        load_holdout_cases(path)


def test_load_holdout_cases_rejects_duplicate_ids(tmp_path):
    cases = [_holdout_case("eval-v1-25") for _ in range(6)]
    path = tmp_path / "holdout_cases.json"
    _write_cases(path, cases)

    with pytest.raises(BenchmarkError, match="unique"):
        load_holdout_cases(path)


def test_raw_fields_holdout_flag_marks_trace_as_holdout(tmp_path):
    contract = tmp_path / "contract.json"
    contract.write_text("{}", encoding="utf-8")
    fields = _raw_fields(
        run_id="t20-test",
        trace_id="t20-test-1",
        case={"case_id": "eval-v1-25", "source_row_id": 1241, "answer_type": "boolean"},
        scheduled={"condition_id": "B0_buffered_256", "repetition": 0},
        evidence={
            "dataset": {"repository": "rag-datasets/rag-mini-wikipedia", "revision": "abc"},
            "corpus_hash": "corpus",
            "index_snapshot": "index",
        },
        preflight={
            "model": "qwen3:4b-instruct",
            "identity": {"ollama_version": "0.32.13", "model_digest": "sha256:test"},
        },
        contract=contract,
        holdout=True,
    )

    assert fields["holdout"] is True
    assert fields["server_state"] == "holdout-qualified"
    assert fields["power_mode"] == "holdout-serial"


def test_raw_fields_default_is_development_mode():
    import pathlib
    import hashlib
    contract = pathlib.Path(__file__).parent.parent / "contracts" / "behavioral_contract.v1.json"
    fields = _raw_fields(
        run_id="t16-test",
        trace_id="t16-test-1",
        case={"case_id": "eval-v1-01", "source_row_id": 1, "answer_type": "boolean"},
        scheduled={"condition_id": "B0_buffered_256", "repetition": 0},
        evidence={
            "dataset": {"repository": "rag-datasets/rag-mini-wikipedia", "revision": "abc"},
            "corpus_hash": "corpus",
            "index_snapshot": "index",
        },
        preflight={
            "model": "qwen3:4b-instruct",
            "identity": {"ollama_version": "0.32.13", "model_digest": "sha256:test"},
        },
        contract=contract,
    )

    assert fields["holdout"] is False
    assert fields["server_state"] == "preflight-qualified"
    assert fields["power_mode"] == "authoritative-serial"
