#!/usr/bin/env python3
"""Bounded, evidence-preserving vLLM-Metal M05 feasibility runner."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
import re
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from typing import Any


GIB = 1024**3
MIB = 1024**2
DEFAULT_MODEL = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
DEFAULT_REVISION = "2fd8dac"


def _solid_png(red: int, green: int, blue: int) -> str:
    width = height = 32
    raw = b"".join(b"\x00" + bytes((red, green, blue)) * width for _ in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return base64.b64encode(png).decode()


def make_image_fixtures() -> dict[str, dict[str, str]]:
    return {
        "black": {"expected_color": "black", "data_url": f"data:image/png;base64,{_solid_png(0, 0, 0)}"},
        "red": {"expected_color": "red", "data_url": f"data:image/png;base64,{_solid_png(255, 0, 0)}"},
    }


def cache_correctness_reasons(enabled: list[dict[str, Any]], disabled: list[dict[str, Any]]) -> list[str]:
    if len(enabled) < 3 or len(disabled) < 3 or any(not item.get("ok") for item in enabled[:3] + disabled[:3]):
        return ["cache_probe_incomplete"]
    enabled_outputs = [str(item.get("output", "")).strip().lower() for item in enabled[:3]]
    disabled_outputs = [str(item.get("output", "")).strip().lower() for item in disabled[:3]]
    reasons = []
    if enabled_outputs != disabled_outputs:
        reasons.append("cache_output_parity_failed")
    if "black" not in enabled_outputs[1] or "red" not in enabled_outputs[2] or "black" not in disabled_outputs[1] or "red" not in disabled_outputs[2]:
        reasons.append("image_identity_failed")
    return reasons


def has_sustained_swap(samples: list[int], threshold: int) -> bool:
    return any(b - a >= threshold and c - b >= threshold for a, b, c in zip(samples, samples[1:], samples[2:]))


def assess_condition(*, device: str, server_log: str, request_results: list[dict[str, Any]], memory_samples: list[dict[str, Any]], capacity_bytes: int, safety_margin_bytes: int, sustained_swap_bytes: int) -> dict[str, Any]:
    reasons: list[str] = []
    if "gpu" not in device.lower():
        reasons.append("device_is_not_gpu")
    if "metal worker" not in server_log.lower():
        reasons.append("metal_worker_not_observed")
    if any(not item.get("ok") for item in request_results):
        reasons.append("request_failed")
    if max((int(item.get("rss_bytes") or 0) for item in memory_samples), default=0) > capacity_bytes - safety_margin_bytes:
        reasons.append("memory_headroom_exceeded")
    swaps = [int(item.get("swap_used_bytes") or 0) for item in memory_samples]
    if has_sustained_swap(swaps, sustained_swap_bytes):
        reasons.append("sustained_swap")
    return {"status": "pass" if not reasons else "fail", "reasons": reasons}


def summary_status(records: list[dict[str, Any]], *, selected_fraction: float | None) -> str:
    if selected_fraction is None:
        return "fail"
    required = {f"memory_fraction_{selected_fraction:.2f}", "cache_disabled", "cache_enabled", "concurrency_2", "concurrency_4"}
    by_name = {str(record["name"]): record for record in records}
    return "pass" if all(by_name.get(name, {}).get("acceptance", {}).get("status") == "pass" for name in required) else "fail"


def _command_output(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _swap_used_bytes() -> int | None:
    output = _command_output(["sysctl", "vm.swapusage"])
    match = re.search(r"used = ([0-9.]+)([MGT])", output)
    if not match:
        return None
    return int(float(match.group(1)) * {"M": MIB, "G": GIB, "T": 1024 * GIB}[match.group(2)])


def memory_snapshot(label: str, process: subprocess.Popen[str] | None) -> dict[str, Any]:
    rss_bytes = None
    if process and process.poll() is None:
        output = _command_output(["ps", "-o", "rss=", "-p", str(process.pid)])
        try:
            rss_bytes = int(output) * 1024
        except ValueError:
            pass
    return {"label": label, "captured_at_unix_s": time.time(), "rss_bytes": rss_bytes, "swap_used_bytes": _swap_used_bytes(), "vm_stat": _command_output(["vm_stat"])}


def _request_json(url: str, payload: dict[str, Any], timeout: float = 120) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _wait_ready(base_url: str, process: subprocess.Popen[str], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited before readiness (code {process.returncode})")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError, TimeoutError):
            time.sleep(1)
    raise TimeoutError(f"server did not become ready within {timeout:.0f}s")


def _device_evidence() -> str:
    return _command_output([sys.executable, "-c", "import mlx.core as mx; print(mx.default_device())"])


def _chat(base_url: str, model: str, content: list[dict[str, Any]] | str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        response = _request_json(f"{base_url}/v1/chat/completions", {"model": model, "messages": [{"role": "user", "content": content}], "max_tokens": 16, "temperature": 0})
        text = response["choices"][0]["message"]["content"]
        return {"ok": True, "elapsed_ms": round((time.monotonic() - started) * 1000, 3), "output": text, "response": response}
    except Exception as exc:
        return {"ok": False, "elapsed_ms": round((time.monotonic() - started) * 1000, 3), "error": f"{type(exc).__name__}: {exc}"}


def _server_command(args: argparse.Namespace, fraction: float, cache_enabled: bool) -> tuple[list[str], dict[str, str]]:
    command = [sys.executable, "-m", "vllm.entrypoints.openai.api_server", "--model", args.model, "--revision", args.revision, "--port", str(args.port), "--max-model-len", "4096", "--max-num-seqs", str(args.max_num_seqs), "--limit-mm-per-prompt", '{"image":2}']
    if cache_enabled:
        command.append("--enable-prefix-caching")
    env = os.environ.copy()
    env.update({"VLLM_MLX_DEVICE": "gpu", "VLLM_METAL_USE_PAGED_ATTENTION": "1", "VLLM_METAL_MULTIMODAL_MODE": "multimodal-native", "VLLM_METAL_DECODE_PIPELINE": "1", "MLX_MAX_OPS_PER_BUFFER": "2000", "VLLM_METAL_MEMORY_FRACTION": str(fraction)})
    return command, env


def _one_condition(args: argparse.Namespace, *, name: str, fraction: float, cache_enabled: bool, concurrency: int, warm: bool) -> dict[str, Any]:
    command, env = _server_command(args, fraction, cache_enabled)
    evidence: dict[str, Any] = {"schema_version": "m05-condition.v1", "name": name, "command": command, "environment": {key: env[key] for key in ("VLLM_MLX_DEVICE", "VLLM_METAL_MEMORY_FRACTION", "VLLM_METAL_USE_PAGED_ATTENTION", "VLLM_METAL_MULTIMODAL_MODE", "VLLM_METAL_DECODE_PIPELINE", "MLX_MAX_OPS_PER_BUFFER")}, "device": _device_evidence(), "cache_enabled": cache_enabled, "concurrency": concurrency, "warm": warm, "memory_samples": [], "requests": []}
    process: subprocess.Popen[str] | None = None
    try:
        evidence["memory_samples"].append(memory_snapshot("before_start", None))
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        _wait_ready(f"http://127.0.0.1:{args.port}", process, args.startup_timeout)
        evidence["memory_samples"].append(memory_snapshot("after_load", process))
        fixtures = make_image_fixtures()
        payloads: list[list[dict[str, Any]] | str] = ["Reply with exactly READY."]
        for fixture in fixtures.values():
            payloads.append([{"type": "text", "text": "What is the dominant color? Reply with one word."}, {"type": "image_url", "image_url": {"url": fixture["data_url"]}}])
        if warm:
            _chat(f"http://127.0.0.1:{args.port}", args.model, "Reply with exactly READY.")
        for payload in payloads:
            evidence["requests"].append(_chat(f"http://127.0.0.1:{args.port}", args.model, payload))
            evidence["memory_samples"].append(memory_snapshot("after_request", process))
        if concurrency > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                evidence["requests"].extend(executor.map(lambda _: _chat(f"http://127.0.0.1:{args.port}", args.model, "Reply with exactly READY."), range(concurrency)))
            evidence["memory_samples"].append(memory_snapshot("after_concurrency", process))
    except Exception as exc:
        evidence["requests"].append({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            evidence["server_log_tail"] = process.stdout.read()[-8000:] if process.stdout else ""
        evidence["memory_samples"].append(memory_snapshot("after_shutdown", None))
    evidence["acceptance"] = assess_condition(device=str(evidence["device"]), server_log=str(evidence.get("server_log_tail", "")), request_results=evidence["requests"], memory_samples=evidence["memory_samples"], capacity_bytes=args.capacity_gib * GIB, safety_margin_bytes=args.safety_margin_gib * GIB, sustained_swap_bytes=args.sustained_swap_mib * MIB)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--startup-timeout", type=float, default=300)
    parser.add_argument("--fractions", default="0.60,0.70,0.80")
    parser.add_argument("--capacity-gib", type=int, default=24)
    parser.add_argument("--safety-margin-gib", type=int, default=4)
    parser.add_argument("--sustained-swap-mib", type=int, default=64)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fractions = [float(value) for value in args.fractions.split(",")]
    records = []
    for fraction in fractions:
        name = f"memory_fraction_{fraction:.2f}"
        record = _one_condition(args, name=name, fraction=fraction, cache_enabled=False, concurrency=1, warm=False)
        (args.output_dir / f"{name}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        records.append(record)
    safe_fractions = [fraction for fraction, record in zip(fractions, records) if record["acceptance"]["status"] == "pass"]
    if safe_fractions:
        selected = max(safe_fractions)
        for name, cache_enabled, concurrency, warm in (("cache_disabled", False, 1, True), ("cache_enabled", True, 1, True), ("concurrency_2", True, 2, True), ("concurrency_4", True, 4, True)):
            record = _one_condition(args, name=name, fraction=selected, cache_enabled=cache_enabled, concurrency=concurrency, warm=warm)
            (args.output_dir / f"{name}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            records.append(record)
    by_name = {record["name"]: record for record in records}
    if safe_fractions:
        cache_reasons = cache_correctness_reasons(by_name["cache_enabled"]["requests"], by_name["cache_disabled"]["requests"])
        for name in ("cache_enabled", "cache_disabled"):
            by_name[name]["cache_validation"] = {"status": "pass" if not cache_reasons else "fail", "reasons": cache_reasons}
            if cache_reasons:
                by_name[name]["acceptance"]["status"] = "fail"
                by_name[name]["acceptance"]["reasons"].extend(reason for reason in cache_reasons if reason not in by_name[name]["acceptance"]["reasons"])
            (args.output_dir / f"{name}.json").write_text(json.dumps(by_name[name], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"schema_version": "m05-summary.v1", "capacity_gib": args.capacity_gib, "safety_margin_gib": args.safety_margin_gib, "selected_memory_fraction": max(safe_fractions) if safe_fractions else None, "conditions": [{"name": item["name"], "status": item["acceptance"]["status"], "reasons": item["acceptance"]["reasons"]} for item in records]}
    summary["status"] = summary_status(records, selected_fraction=summary["selected_memory_fraction"])
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
