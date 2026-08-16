import json
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.preflight_ollama import (
    PreflightError,
    leakage,
    model_digest,
    run,
    validate_local_url,
)


def test_endpoint_must_be_loopback_http():
    assert validate_local_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434"
    with pytest.raises(PreflightError):
        validate_local_url("https://example.com")
    with pytest.raises(PreflightError):
        validate_local_url("http://10.0.0.2:11434")


def test_digest_requires_sha256(monkeypatch):
    digest = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
    monkeypatch.setattr("scripts.preflight_ollama.http_json", lambda *args: {"models": [{"name": "qwen3:4b", "digest": f"sha256:{digest}"}]})
    assert model_digest("http://127.0.0.1:11434", "qwen3:4b", 1) == f"sha256:{digest}"
    monkeypatch.setattr("scripts.preflight_ollama.http_json", lambda *args: {"models": [{"name": "qwen3:4b", "digest": None}]})
    with pytest.raises(PreflightError, match="digest"):
        model_digest("http://127.0.0.1:11434", "qwen3:4b", 1)


def test_digest_normalizes_ollama_bare_sha256_value(monkeypatch):
    bare_digest = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
    monkeypatch.setattr(
        "scripts.preflight_ollama.http_json",
        lambda *args: {"models": [{"name": "qwen3:4b", "digest": bare_digest}]},
    )
    assert model_digest("http://127.0.0.1:11434", "qwen3:4b", 1) == f"sha256:{bare_digest}"


def test_reasoning_leakage_is_observable_only():
    assert not leakage({"response": "READY"})
    assert leakage({"thinking": "hidden chain"})
    assert leakage({"response": "<think>hidden</think>READY"})


def test_run_records_explicit_failure_and_never_passes_without_digest(monkeypatch):
    monkeypatch.setattr("scripts.preflight_ollama.version", lambda *args: "0.12.3")
    monkeypatch.setattr("scripts.preflight_ollama.model_digest", lambda *args: (_ for _ in ()).throw(PreflightError("digest_missing", "missing")))
    result = run(Namespace(base_url="http://127.0.0.1:11434", model="qwen3:4b", timeout=1, pull_timeout=1, pull=False))
    assert result["status"] == "blocked"
    assert result["failures"] == [{"error_type": "digest_missing", "message": "missing"}]


def test_run_validates_buffered_stream_terminal_and_parity(monkeypatch):
    monkeypatch.setattr("scripts.preflight_ollama.version", lambda *args: "0.12.3")
    monkeypatch.setattr("scripts.preflight_ollama.model_digest", lambda *args: "sha256:abc")
    monkeypatch.setattr("scripts.preflight_ollama.request_buffered", lambda *args: ("READY", {"done": True, "eval_count": 1}, 1.0))
    monkeypatch.setattr("scripts.preflight_ollama.request_streaming", lambda *args: ("READY", [{"response": "READY"}, {"done": True, "eval_count": 1}], 1.0))
    result = run(Namespace(base_url="http://127.0.0.1:11434", model="qwen3:4b", timeout=1, pull_timeout=1, pull=False))
    assert result["status"] == "pass"
    assert result["smoke"]["final_text_parity"] is True
    assert result["smoke"]["streaming"]["terminal"]["done"] is True


def test_artifact_is_json_when_present():
    artifact = Path("artifacts/ollama_preflight.v1.json")
    if artifact.exists():
        data = json.loads(artifact.read_text())
        assert data["schema_version"] == "ollama-preflight.v1"
