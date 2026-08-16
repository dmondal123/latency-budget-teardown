"""End-to-end retrieval-trace fixtures for buffered and streamed display."""

import json

import pytest

from scripts.ingestion.corpus import ingest_passages
from scripts.ollama_client import OllamaClient
from scripts.pipeline import run_request
from scripts.retrieval import build_index


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 10
        return self.value


def raw_fields(index, *, condition_id):
    return {
        "run_id": "run-e2e", "trace_id": condition_id, "case_id": "case-paris", "source_row_id": "row-1",
        "condition_id": condition_id, "repetition": 1, "attempt": 1, "answer_type": "short", "holdout": False,
        "server_state": "warm", "cache_state": "off", "dataset_repo": "fixture", "dataset_revision": "fixture-v1",
        "corpus_hash": index.corpus_hash, "index_snapshot": index.index_snapshot, "model_tag": "qwen3:4b-instruct",
        "model_digest": "fixture-digest", "think_mode": False, "ollama_version": "fixture", "prompt_hash": "fixture-prompt",
        "contract_hash": "fixture-contract", "python_version": "3.12", "macos_build": "fixture", "chip": "fixture",
        "ram_bytes": 1, "power_mode": "fixture",
    }


@pytest.fixture
def index():
    return build_index(ingest_passages([
        {"id": 42, "passage": "Paris is the capital of France."},
        {"id": 7, "passage": "Berlin is the capital of Germany."},
        {"id": 9, "passage": "Oceans cover much of the Earth."},
    ], corpus_hash="a" * 64))


@pytest.mark.parametrize("stream_mode", [False, True], ids=["buffered", "streamed"])
def test_pipeline_persists_complete_validated_retrieval_trace(tmp_path, index, stream_mode):
    payloads, displayed = [], []
    answer = '{"answer":"Paris","abstained":false,"citations":["SOURCE_1"]}'

    def transport(payload, stream):
        payloads.append((payload, stream))
        return [json.dumps({"response": answer[:14]}).encode() + b"\n", json.dumps({"response": answer[14:], "done": True, "eval_count": 9}).encode() + b"\n"]

    row = run_request(
        question="What is the capital of France?", index=index, client=OllamaClient(transport=transport),
        raw_fields=raw_fields(index, condition_id=f"{'I1' if stream_mode else 'B0'}_fixture"), trace_path=tmp_path / "trace.jsonl",
        validation_path=tmp_path / "validation.jsonl", stream_mode=stream_mode, clock=Clock(), display=displayed.append,
    )

    assert payloads[0][0]["think"] is False
    assert payloads[0][1] is stream_mode
    assert row["raw_output"] == answer
    assert row["retrieved_evidence_ids"] == ["passage:42"]
    assert row["admitted_evidence_ids"] == ["passage:42"]
    assert row["fatal_gates"] == []
    assert row["scores"] == {"validation_valid": True, "citation_ids": [42]}
    assert row["ttc_ms"] == sum(row[f"{stage}_ms"] for stage in ("admission", "retrieval", "context_assembly", "model_dispatch_to_first_token", "model_decode", "validation"))
    assert (row["first_token_displayed_ms"] < row["ttc_ms"]) is stream_mode
    assert displayed == ([answer[:14], answer[14:]] if stream_mode else [answer])
    assert len((tmp_path / "trace.jsonl").read_text().splitlines()) == 1
    assert len((tmp_path / "validation.jsonl").read_text().splitlines()) == 1


def test_buffered_and_streamed_fixtures_have_deterministic_final_text_parity(tmp_path, index):
    rows = []
    for stream_mode in (False, True):
        answer = '{"answer":"Paris","abstained":false,"citations":["SOURCE_1"]}'
        client = OllamaClient(transport=lambda *_: [json.dumps({"response": answer, "done": True}).encode() + b"\n"])
        rows.append(run_request(question="What is the capital of France?", index=index, client=client,
            raw_fields=raw_fields(index, condition_id=str(stream_mode)), trace_path=tmp_path / f"{stream_mode}.jsonl",
            validation_path=tmp_path / f"{stream_mode}.validation.jsonl", stream_mode=stream_mode, clock=Clock()))
    assert rows[0]["raw_output"] == rows[1]["raw_output"]
