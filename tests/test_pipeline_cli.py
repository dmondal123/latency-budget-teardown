"""CLI contract for a full, trace-persisted manual RAG query."""

import json

from scripts.ingestion.corpus import ingest_passages
from scripts.pipeline import main


def test_main_runs_validated_streamed_query_and_writes_manual_artifacts(tmp_path, monkeypatch, capsys):
    manifest = ingest_passages([
        {"id": 42, "passage": "Paris is the capital of France."},
        {"id": 7, "passage": "Berlin is the capital of Germany."},
        {"id": 9, "passage": "Oceans cover much of the Earth."},
    ], corpus_hash="a" * 64)
    manifest["dataset"] = {"repository": "fixture-repo", "revision": "fixture-revision"}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps({"identity": {"model_digest": "fixture-digest", "ollama_version": "fixture"}, "think": False}), encoding="utf-8")
    contract_path = tmp_path / "contract.json"
    contract_path.write_text("{}", encoding="utf-8")
    answer = '{"answer":"Paris","abstained":false,"citations":["SOURCE_1"]}'

    class FakeClient:
        def generate(self, _prompt, *, stream, max_tokens, on_response_chunk):
            assert stream is True
            assert max_tokens == 128
            on_response_chunk(answer)
            return type("Result", (), {"text": answer, "finish_reason": "stop", "output_tokens": 9})()

    monkeypatch.setattr("scripts.pipeline.OllamaClient", FakeClient)
    output_dir = tmp_path / "manual"

    assert main([
        "--manifest", str(manifest_path), "--preflight", str(preflight_path), "--contract", str(contract_path),
        "--question", "What is the capital of France?", "--stream", "--max-tokens", "128", "--output-dir", str(output_dir),
    ]) == 0

    assert json.loads(capsys.readouterr().out) == json.loads(answer)
    trace = json.loads(next(output_dir.glob("*.trace.jsonl")).read_text())
    assert trace["dataset_repo"] == "fixture-repo"
    assert trace["model_digest"] == "fixture-digest"
    assert trace["think_mode"] is False
    assert trace["fatal_gates"] == []
    assert len(list(output_dir.glob("*.validation.jsonl"))) == 1
