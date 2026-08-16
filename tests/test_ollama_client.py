"""Ollama client contracts without a live model."""

import io
import pytest

from scripts.ollama_client import OllamaClient, OllamaClientError, parse_ndjson


def test_stream_parser_requires_done_terminal_and_concatenates_deltas():
    result = parse_ndjson([b'{"response":"Hel"}\n', b'{"response":"lo","done":true,"eval_count":2}\n'])
    assert result.text == "Hello"
    assert result.finish_reason == "stop"
    with pytest.raises(OllamaClientError, match="terminal"):
        parse_ndjson([b'{"response":"hello"}\n'])


def test_client_sends_pinned_thinking_disabled_request_and_never_retries():
    payloads = []

    def transport(payload, stream):
        payloads.append((payload, stream))
        return [b'{"response":"ok","done":true}\n']

    result = OllamaClient(transport=transport).generate("Question", stream=True, max_tokens=128)
    assert result.text == "ok"
    assert len(payloads) == 1
    assert payloads[0] == (
        {"model": "qwen3:4b-instruct", "prompt": "Question", "stream": True, "think": False,
         "keep_alive": "5m", "options": {"temperature": 0, "seed": 20260816, "num_predict": 128}},
        True,
    )


def test_default_client_uses_loopback_generate_endpoint(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return io.BytesIO(b'{"response":"ok","done":true}\n')

        def __exit__(self, *_args):
            return None

    def open_request(request, timeout):
        seen["url"] = request.full_url
        seen["payload"] = request.data
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr("scripts.ollama_client.urllib.request.urlopen", open_request)
    result = OllamaClient(timeout=7).generate("Question", stream=False, max_tokens=8)
    assert result.text == "ok"
    assert seen["url"] == "http://127.0.0.1:11434/api/generate"
    assert seen["timeout"] == 7


def test_default_client_delivers_each_network_chunk_before_reading_the_next(monkeypatch):
    events = []

    class Response:
        def __enter__(self):
            events.append("opened")
            return self

        def __exit__(self, *_args):
            events.append("closed")

        def __iter__(self):
            events.append("received:first")
            yield b'{"response":"first"}\n'
            events.append("received:second")
            yield b'{"response":"second","done":true}\n'

    monkeypatch.setattr("scripts.ollama_client.urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    result = OllamaClient().generate(
        "Question", stream=True, max_tokens=8, on_response_chunk=lambda chunk: events.append(f"displayed:{chunk}")
    )

    assert result.text == "firstsecond"
    assert events == [
        "opened", "received:first", "displayed:first", "received:second", "displayed:second", "closed",
    ]
