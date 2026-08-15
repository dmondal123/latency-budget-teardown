#!/usr/bin/env python3
"""Run bounded text, image, and device smoke checks against vLLM-Metal."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
PNG_DATA = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

def request_json(url: str, payload: dict | None = None, timeout: float = 10) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())

def wait_ready(base_url: str, process: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited before readiness (code {process.returncode})")
        try:
            request_json(f"{base_url}/health", timeout=2)
            return
        except (OSError, urllib.error.URLError, TimeoutError):
            time.sleep(1)
    raise TimeoutError(f"server did not become ready within {timeout:.0f}s")

def chat(base_url: str, model: str, content: list[dict] | str) -> dict:
    return request_json(f"{base_url}/v1/chat/completions", {"model": model, "messages": [{"role": "user", "content": content}], "max_tokens": 16, "temperature": 0}, timeout=120)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--revision", default="2fd8dac")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--startup-timeout", type=float, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base_url = f"http://127.0.0.1:{args.port}"
    command = [sys.executable, "-m", "vllm.entrypoints.openai.api_server", "--model", args.model, "--revision", args.revision, "--port", str(args.port), "--max-model-len", "2048", "--limit-mm-per-prompt", "image=2"]
    env = os.environ.copy()
    env.update({"VLLM_METAL_USE_MLX": "1", "VLLM_MLX_DEVICE": "gpu", "VLLM_METAL_MULTIMODAL_MODE": "multimodal-native"})
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    result: dict[str, object] = {"schema_version": "runtime-smoke.v1", "model": args.model, "revision": args.revision, "command": command}
    try:
        wait_ready(base_url, process, args.startup_timeout)
        result["health"] = "pass"
        result["text"] = chat(base_url, args.model, "Reply with exactly the word READY.")
        result["image"] = chat(base_url, args.model, [{"type": "text", "text": "What is the dominant color in this image? Answer one word."}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG_DATA}"}}])
        result["status"] = "pass"
    except Exception as exc:
        result["status"] = "fail"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if process.stdout:
            result["server_log_tail"] = process.stdout.read()[-4000:]
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "pass" else 1

if __name__ == "__main__":
    raise SystemExit(main())
