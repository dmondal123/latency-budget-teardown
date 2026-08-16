#!/usr/bin/env python3
"""Bounded Ollama identity and buffered/NDJSON smoke preflight.

The Ollama HTTP API is deliberately treated as an opaque local service.  This
script records observable response metadata only; it does not infer engine
queue or prefill timings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MODEL = "qwen3:4b"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
PROMPT = "Reply with exactly the word READY."
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class PreflightError(RuntimeError):
    """A reproducible preflight failure with a stable category."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


def validate_local_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in LOCAL_HOSTS:
        raise PreflightError("non_local_endpoint", "endpoint must be plain HTTP on localhost/loopback")
    if parsed.path or parsed.params or parsed.query or parsed.fragment:
        raise PreflightError("invalid_endpoint", "base URL must not contain a path, query, or fragment")
    return base_url.rstrip("/")


def http_json(base_url: str, path: str, payload: dict[str, Any] | None, timeout: float) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PreflightError("service_unavailable", f"{path}: {type(exc).__name__}: {exc}") from exc


def version(base_url: str, timeout: float) -> str:
    try:
        value = http_json(base_url, "/api/version", None, timeout).get("version")
    except PreflightError:
        raise
    if not value:
        raise PreflightError("version_missing", "Ollama version response did not contain version")
    return str(value)


def pull_model(base_url: str, model: str, timeout: float) -> dict[str, Any]:
    # The pull endpoint is NDJSON. Consume it fully so the model is ready.
    request = urllib.request.Request(
        f"{base_url}/api/pull",
        data=json.dumps({"model": model, "stream": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last: dict[str, Any] = {}
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for line in response:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"pull exceeded {timeout:.0f}s wall-clock bound")
                if line.strip():
                    last = json.loads(line)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PreflightError("pull_failed", f"{type(exc).__name__}: {exc}") from exc
    if last.get("error"):
        raise PreflightError("pull_failed", str(last["error"]))
    return last


def model_digest(base_url: str, model: str, timeout: float) -> str:
    tags = http_json(base_url, "/api/tags", None, timeout)
    for item in tags.get("models", []):
        if item.get("name") == model and item.get("digest"):
            digest = str(item["digest"])
            bare_digest = digest.removeprefix("sha256:")
            if re.fullmatch(r"[0-9a-fA-F]{64}", bare_digest):
                return f"sha256:{bare_digest.lower()}"
    raise PreflightError("digest_missing", f"no immutable sha256 digest found for {model}")


def request_buffered(base_url: str, model: str, timeout: float) -> tuple[str, dict[str, Any], float]:
    started = time.perf_counter_ns()
    result = http_json(
        base_url,
        "/api/generate",
        {"model": model, "prompt": PROMPT, "stream": False, "think": False, "options": {"temperature": 0, "seed": 20260816}},
        timeout,
    )
    elapsed = (time.perf_counter_ns() - started) / 1_000_000
    text = str(result.get("response") or result.get("message", {}).get("content") or "")
    return text, result, elapsed


def request_streaming(base_url: str, model: str, timeout: float) -> tuple[str, list[dict[str, Any]], float]:
    request = urllib.request.Request(
        f"{base_url}/api/generate",
        data=json.dumps({"model": model, "prompt": PROMPT, "stream": True, "think": False, "options": {"temperature": 0, "seed": 20260816}}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chunks: list[dict[str, Any]] = []
    started = time.perf_counter_ns()
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for line in response:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"stream exceeded {timeout:.0f}s wall-clock bound")
                if line.strip():
                    chunks.append(json.loads(line))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PreflightError("stream_failed", f"{type(exc).__name__}: {exc}") from exc
    elapsed = (time.perf_counter_ns() - started) / 1_000_000
    text = "".join(str(c.get("response") or c.get("message", {}).get("content") or "") for c in chunks)
    return text, chunks, elapsed


def leakage(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("thinking") or value.get("thoughts"):
            return True
        return any(leakage(item) for item in value.values())
    if isinstance(value, list):
        return any(leakage(item) for item in value)
    return isinstance(value, str) and ("<think>" in value.lower() or "</think>" in value.lower())


def failure(error_type: str, message: str) -> dict[str, str]:
    return {"error_type": error_type, "message": message}


def run(args: argparse.Namespace) -> dict[str, Any]:
    base_url = validate_local_url(args.base_url)
    result: dict[str, Any] = {
        "schema_version": "ollama-preflight.v1",
        "status": "blocked",
        "model": args.model,
        "endpoint": base_url,
        "local_only": True,
        "think": False,
        "temperature": 0,
        "seed": 20260816,
        "resource_checks": {"sustained_swap": None, "reason": "not observable because Ollama preflight was blocked"},
        "identity": {"ollama_version": None, "model_digest": None},
        "smoke": {"buffered": None, "streaming": None, "final_text_parity": False},
        "failures": [],
        "command": "python scripts/preflight_ollama.py",
    }
    try:
        result["identity"]["ollama_version"] = version(base_url, args.timeout)
        if args.pull:
            result["pull"] = pull_model(base_url, args.model, args.pull_timeout)
        result["identity"]["model_digest"] = model_digest(base_url, args.model, args.timeout)
        buffered_text, buffered_raw, buffered_ms = request_buffered(base_url, args.model, args.timeout)
        streaming_text, stream_chunks, streaming_ms = request_streaming(base_url, args.model, args.timeout)
        terminal = stream_chunks[-1] if stream_chunks else {}
        buffered_ok = bool(buffered_text.strip()) and not leakage(buffered_raw)
        streaming_ok = bool(streaming_text.strip()) and bool(terminal.get("done")) and not leakage(stream_chunks)
        result["smoke"] = {
            "buffered": {"status": "pass" if buffered_ok else "fail", "text": buffered_text, "elapsed_ms": buffered_ms, "metadata": {k: buffered_raw.get(k) for k in ("done", "done_reason", "prompt_eval_count", "eval_count", "total_duration", "load_duration", "prompt_eval_duration", "eval_duration")}},
            "streaming": {"status": "pass" if streaming_ok else "fail", "text": streaming_text, "elapsed_ms": streaming_ms, "chunk_count": len(stream_chunks), "terminal": terminal, "metadata": {k: terminal.get(k) for k in ("done", "done_reason", "prompt_eval_count", "eval_count", "total_duration", "load_duration", "prompt_eval_duration", "eval_duration")}},
            "final_text_parity": buffered_text == streaming_text,
        }
        if not buffered_ok:
            result["failures"].append(failure("buffered_invalid", "buffered response was empty or exposed reasoning"))
        if not streaming_ok:
            result["failures"].append(failure("stream_invalid", "stream lacked non-empty text, terminal done metadata, or exposed reasoning"))
        if buffered_text != streaming_text:
            result["failures"].append(failure("final_text_mismatch", "buffered and streamed final text differ"))
        result["status"] = "pass" if not result["failures"] else "fail"
    except PreflightError as exc:
        result["failures"].append(failure(exc.error_type, str(exc)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--pull-timeout", type=float, default=1800)
    parser.add_argument("--no-pull", dest="pull", action="store_false")
    parser.add_argument("--output", type=Path, default=Path("artifacts/ollama_preflight.v1.json"))
    args = parser.parse_args()
    started = time.perf_counter_ns()
    try:
        result = run(args)
    except PreflightError as exc:
        result = {"schema_version": "ollama-preflight.v1", "status": "blocked", "endpoint": args.base_url, "local_only": False, "failures": [failure(exc.error_type, str(exc))]}
    result["elapsed_ms"] = (time.perf_counter_ns() - started) / 1_000_000
    result["invocation"] = " ".join(sys.argv)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
