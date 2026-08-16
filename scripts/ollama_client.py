"""Strict, local-only Ollama generate client with deterministic request shape."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class ModelResult:
    text: str
    finish_reason: str
    output_tokens: int | None


class OllamaClientError(RuntimeError):
    pass


def parse_ndjson(
    lines: Iterable[bytes], *, on_response_chunk: Callable[[str], None] | None = None
) -> ModelResult:
    chunks: list[dict[str, object]] = []
    for raw in lines:
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaClientError("malformed NDJSON") from exc
        if not isinstance(item, dict):
            raise OllamaClientError("NDJSON chunks must be objects")
        if item.get("error"):
            raise OllamaClientError(str(item["error"]))
        chunks.append(item)
        response = item.get("response")
        if on_response_chunk is not None and isinstance(response, str) and response:
            on_response_chunk(response)
    if not chunks or chunks[-1].get("done") is not True:
        raise OllamaClientError("stream is missing a done terminal")
    text = "".join(str(chunk.get("response") or "") for chunk in chunks)
    terminal = chunks[-1]
    return ModelResult(text, str(terminal.get("done_reason") or "stop"), terminal.get("eval_count") if isinstance(terminal.get("eval_count"), int) else None)


class OllamaClient:
    def __init__(
        self,
        *,
        transport: Callable[[dict[str, object], bool], Iterable[bytes]] | None = None,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 30,
    ) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.path not in {"", "/"}:
            raise OllamaClientError("Ollama endpoint must be loopback HTTP without a path")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport or self._request

    def _request(self, payload: dict[str, object], _stream: bool) -> Iterable[bytes]:
        request = urllib.request.Request(
            f"{self._base_url}/api/generate", data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return tuple(response)
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            raise OllamaClientError(f"service_unavailable: {type(exc).__name__}: {exc}") from exc

    def generate(
        self,
        prompt: str,
        *,
        stream: bool,
        max_tokens: int,
        on_response_chunk: Callable[[str], None] | None = None,
    ) -> ModelResult:
        payload: dict[str, object] = {
            "model": "qwen3:4b-instruct", "prompt": prompt, "stream": stream, "think": False, "keep_alive": "5m",
            "options": {"temperature": 0, "seed": 20260816, "num_predict": max_tokens},
        }
        return parse_ndjson(self._transport(payload, stream), on_response_chunk=on_response_chunk)
