"""Offline T17/T18/T19 evidence generation from an immutable T16 run.

This module is the single offline CLI for regenerating the corrected T17 latency
reports, T18 quality/gate inputs, and T19 budget/provenance evidence from one
saved authoritative run.  It never calls Ollama, reruns a benchmark, or opens
sealed holdouts; it consumes only persisted raw traces, validation records,
warmups, and the run manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .answer_validation import validate_answer
from .evaluation import (
    FROZEN_CONTRACT_ID,
    FROZEN_THRESHOLDS,
    REGISTERED_CONDITIONS,
    grade_citations,
    grade_retrieval,
    grade_text_answer,
    load_jsonl,
    write_condition_report,
)

SEED = 20260816
BOOTSTRAP_RESAMPLES = 10_000

DEFAULT_CASES = Path("eval/v1/development_cases.json")
DEFAULT_HOLDOUT = Path("eval/v1/holdout_manifest.json")
DEFAULT_THRESHOLDS = Path("contracts/thresholds.2026-08-16.json")

# Canonical artifacts inside an authoritative-run directory.
RUN_FILES = ("raw-traces.jsonl", "validations.jsonl", "warmups.jsonl", "run-manifest.json")
MANIFEST_NAME = "report-manifest.json"

# T18/T19 output file names.
T18_NAME = "t18-quality-evidence.json"
T19_JSON_NAME = "t19-evidence.json"
T19_MD_NAME = "t19-evidence.md"

EXPECTED_ATTEMPTS = 360
ATTEMPTS_PER_CONDITION = 120
DEVELOPMENT_CASE_COUNT = 24
REPLICATION_COUNT = 5

# Stages that sum into TTC (mirrors evaluation.CRITICAL_STAGES field names).
TTC_STAGES = (
    "admission",
    "retrieval",
    "context_assembly",
    "model_dispatch_to_first_token",
    "model_decode",
    "validation",
)

# The ten frozen promotion-gate inputs T18 must emit per condition.
GATE_INPUT_KEYS = (
    "fatal_count",
    "retrieval_recall_at_5",
    "citation_precision",
    "citation_validity_rate",
    "task_resolution_rate",
    "answer_token_f1",
    "truncation_rate",
    "p95_ttft_ms",
    "p95_ttc_ms",
    "external_runtime_api_cost_per_completed_task",
)


class ReportError(ValueError):
    """Raised when offline report inputs fail validation."""


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def _require_empty_output(output_dir: Path) -> None:
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise ReportError(f"output directory is not empty: {output_dir}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_and_validate_run(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not run_dir.is_dir():
        raise ReportError(f"run directory does not exist: {run_dir}")
    raw_path = run_dir / "raw-traces.jsonl"
    manifest_path = run_dir / "run-manifest.json"
    for filename in ("raw-traces.jsonl", "run-manifest.json"):
        if not (run_dir / filename).exists():
            raise ReportError(f"missing required run artifact {filename} in {run_dir}")
    traces = load_jsonl(raw_path)
    if len(traces) != EXPECTED_ATTEMPTS:
        raise ReportError(
            f"denominators require {EXPECTED_ATTEMPTS} attempts, found {len(traces)}"
        )
    counts = Counter(str(trace["condition_id"]) for trace in traces)
    for condition in REGISTERED_CONDITIONS:
        if counts.get(condition, 0) != ATTEMPTS_PER_CONDITION:
            raise ReportError(
                f"condition {condition} must have {ATTEMPTS_PER_CONDITION} attempts, "
                f"found {counts.get(condition, 0)}"
            )
    case_ids = {str(trace["case_id"]) for trace in traces}
    if len(case_ids) != DEVELOPMENT_CASE_COUNT:
        raise ReportError(
            f"denominators require {DEVELOPMENT_CASE_COUNT} development cases, found {len(case_ids)}"
        )
    repetitions = {trace["repetition"] for trace in traces}
    if len(repetitions) != REPLICATION_COUNT:
        raise ReportError(
            f"denominators require {REPLICATION_COUNT} repetitions, found {len(repetitions)}"
        )
    if any(trace.get("holdout") for trace in traces):
        raise ReportError("sealed holdout cases are not allowed in the development run")
    run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(run_manifest, dict):
        raise ReportError("run-manifest.json must be a JSON object")
    return traces, run_manifest


def _load_cases(cases_path: Path) -> dict[str, dict[str, Any]]:
    if not cases_path.exists():
        raise ReportError(f"development cases file does not exist: {cases_path}")
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != DEVELOPMENT_CASE_COUNT:
        raise ReportError(
            f"development cases must be exactly {DEVELOPMENT_CASE_COUNT} objects"
        )
    if not all(isinstance(case, dict) for case in data):
        raise ReportError("development cases must all be objects")
    if any(case.get("holdout") for case in data):
        raise ReportError("sealed holdout cases are not allowed in development cases")
    return {str(case["case_id"]): dict(case) for case in data}


def _load_holdout_ids(holdout_manifest_path: Path) -> set[str]:
    if not holdout_manifest_path.exists():
        raise ReportError(f"holdout manifest does not exist: {holdout_manifest_path}")
    manifest = json.loads(holdout_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ReportError("holdout manifest must be a JSON object")
    return {str(case_id) for case_id in manifest.get("case_ids", [])}


def _check_holdout_overlap(traces: Sequence[Mapping[str, Any]], holdout_ids: set[str]) -> None:
    if not holdout_ids:
        return
    overlaps = {str(trace["case_id"]) for trace in traces} & holdout_ids
    if overlaps:
        raise ReportError(
            f"sealed holdout cases cannot appear in the development run: {sorted(overlaps)}"
        )


def _load_thresholds(thresholds_path: Path) -> dict[str, Any]:
    if not thresholds_path.exists():
        raise ReportError(f"thresholds file does not exist: {thresholds_path}")
    data = json.loads(thresholds_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReportError("thresholds file must be a JSON object")
    if "latency_budget_p95_ms" not in data:
        raise ReportError(
            f"thresholds file is missing latency_budget_p95_ms: {thresholds_path}"
        )
    return data


# ---------------------------------------------------------------------------
# Manifest construction
# ---------------------------------------------------------------------------

def _input_hashes(
    run_dir: Path, cases_path: Path, holdout_manifest_path: Path, thresholds_path: Path
) -> tuple[dict[str, str], dict[str, str]]:
    hashes: dict[str, str] = {}
    paths: dict[str, str] = {}
    for key, filename in (
        ("raw_traces", "raw-traces.jsonl"),
        ("validations", "validations.jsonl"),
        ("warmups", "warmups.jsonl"),
        ("run_manifest", "run-manifest.json"),
    ):
        path = run_dir / filename
        if path.exists():
            hashes[key] = _sha256(path)
            paths[key] = str(path)
    for key, path in (
        ("development_cases", cases_path),
        ("holdout_manifest", holdout_manifest_path),
        ("thresholds", thresholds_path),
    ):
        if path.exists():
            hashes[key] = _sha256(path)
            paths[key] = str(path)
    return hashes, paths


def _output_hashes(output_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != MANIFEST_NAME:
            result[path.name] = _sha256(path)
    return result


def _source_run_identity(run_manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_manifest.get("run_id"),
        "status": run_manifest.get("status"),
        "command": run_manifest.get("command"),
        "by_condition": run_manifest.get("by_condition"),
        "c05": run_manifest.get("c05"),
        "live_identity": run_manifest.get("live_identity"),
        "swap_observation": run_manifest.get("swap_observation"),
        "thermal_observation": run_manifest.get("thermal_observation"),
    }


def _build_manifest(
    *,
    run_dir: Path,
    output_dir: Path,
    run_manifest: Mapping[str, Any],
    cases_path: Path,
    holdout_manifest_path: Path,
    thresholds_path: Path,
    command: str,
    seed: int,
    bootstrap_resamples: int,
    traces: list[dict[str, Any]],
    chart_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    input_hashes, input_paths = _input_hashes(run_dir, cases_path, holdout_manifest_path, thresholds_path)
    counts = Counter(str(trace["condition_id"]) for trace in traces)
    manifest: dict[str, Any] = {
        "schema": "offline-reporting-manifest.v1",
        "contract_id": FROZEN_CONTRACT_ID,
        "generated_at": datetime.now(UTC).isoformat(),
        "command": command,
        "seed": seed,
        "bootstrap_resamples": bootstrap_resamples,
        "run_dir": str(run_dir),
        "source_run_identity": _source_run_identity(run_manifest),
        "input_hashes": input_hashes,
        "input_paths": input_paths,
        "conditions": list(REGISTERED_CONDITIONS),
        "denominators": {
            "attempted": len(traces),
            "per_condition": {condition: counts.get(condition, 0) for condition in REGISTERED_CONDITIONS},
            "development_cases": len({str(trace["case_id"]) for trace in traces}),
            "repetitions": len({trace["repetition"] for trace in traces}),
        },
        "chart_metadata": chart_metadata,
        "output_hashes": _output_hashes(output_dir),
    }
    return manifest


# ---------------------------------------------------------------------------
# T18 quality evidence
# ---------------------------------------------------------------------------

def _coerce_evidence_id(value: Any) -> int | None:
    """Coerce a stored evidence id to int.

    Handles ``"passage:N"`` strings and bare ints. Python ``bool`` is a subclass
    of ``int``, so it is rejected explicitly to avoid ``True == 1``.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value[len("passage:"):] if value.startswith("passage:") else value
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _parse_raw_output(raw: Any) -> dict[str, Any] | None:
    """Parse a trace ``raw_output`` JSON blob; return None if missing or malformed."""
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None

def _recompute_validation (trace: Mapping [str, Any]) -> tuple [bool, str | None]:

    """Re-derive fatal status and the gradeable answer from ``raw_output``.
    The run-time ``fatal_gates`` list is not trusted here: a yes/no 
    question answered with a JSON boolean was fatally rejected at run time by the old 
    validator, but is a well-formed answer. We re-run the corrected 
    :func: validate_answer, rebuilding the ``SOURCE_N`` -> evidence-id bindings
    from ``admitted_evidence_ids`` in admission order (the context-assembly 
    labelling convention). A boolean answer is normalised to Yes/No; a 
    truncated/unparseable answer stays fatal. The returned citation ids let the
    caller re-grade citations for rows whose runtime was discarded.
    """
    raw = trace.get("raw_output")
    if not isinstance(raw, str):
        return True, None, ()
    admitted = [
        evidence_id
        for evidence_id in (_coerce_evidence_id(item) for item in trace.get("admitted_evidence_ids", []))
        if evidence_id is not None
    ]
    bindings = {f"SOURCE_{index}": evidence_id for index, evidence_id in enumerate (admitted, start=1)}
    result = validate_answer(raw, bindings)
    parsed = _parse_raw_output(raw)
    answer = parsed.get("answer") if isinstance (parsed, dict) else None
    if isinstance(answer, bool):
        answer = "Yes" if answer else "No"
    answer_text = answer if isinstance(answer, str) else None
    return bool(result.fatal_gates), answer_text, (answer if isinstance(answer, str) else None)



def _mean_available(values: Iterable[float | None]) -> float | None:
    """Mean of non-None values, returning None when every value is unavailable."""
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _grade_attempt(trace: Mapping [str, Any], case: Mapping [str, Any], answer_text: str | None,
citation_override: tuple [int, ...] | None = None,
) -> dict[str, Any]:
    """Grade one attempt's retrieval, citation, and text quality.

Retrieval and citation grades are always computable. ``answer_text is the validated, normalised answer (or ``None when the answer is unavailable /fatally malformed); text grades are ``None in that case rather than raising, so aggregates using : func:'_mean_available' skip them.

``citation_override supplies re-validated citation ids for rows whose run-time citation record was discarded (e.g. a reclassified boolean answer); when ``None`` the persisted ``scores.citation_ids`` are used.

    """
    gold_ids = list(case.get("gold_evidence_ids", []))
    retrieved = [
        evidence_id
        for evidence_id in (_coerce_evidence_id(item) for item in trace.get("retrieved_evidence_ids", []))
        if evidence_id is not None
    ]
    admitted = [
        evidence_id
        for evidence_id in (_coerce_evidence_id(item) for item in trace.get("admitted_evidence_ids", []))
        if evidence_id is not None
    ]

    if citation_override is not None:
        cited = list(citation_override)
    else:
        cited = [
            evidence_id
            for evidence_id in (_coerce_evidence_id(item) for item in trace.get("scores", {}).get("citation_ids", []))
            if evidence_id is not None
        ]
    retrieval = grade_retrieval(retrieved_ids=retrieved, gold_ids=gold_ids)
    citations = grade_citations(cited_ids=cited, admitted_ids=admitted, pinned_ids=gold_ids)
    text: dict[str, Any] | None = None
    if answer_text is not None:
        text = grade_text_answer(
        answer = answer_text,
        reference=case.get("reference_answer", ""),
        answer_type=str(trace.get("answer_type", "")),
        finish_reason=trace.get("finish_reason"),
        )
    return {
        "recall_at_5": retrieval["recall_at_5"],
        "mrr": retrieval["mrr"],
        "citation_precision": citations["citation_precision"],
        "citation_validity_rate": citations["citation_validity_rate"],
        "answer_token_f1": text["answer_token_f1"] if text is not None else None,
        "task_resolution": text["task_resolution"] if text is not None else None,
        "truncated": bool(trace.get("finish_reason") == "length"),
    }


def _aggregate_grades(graded: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate per-attempt grades for one condition over all its attempts.

    Recall/MRR/citation metrics are computed over every attempt (malformed rows
    still expose retrieval evidence and contribute 0.0 citation precision).
    Text metrics skip malformed rows via :func:`_mean_available`.
    """
    count = len(graded)
    fatal_count = sum(1 for record in graded if record["fatal"])
    text_available = sum(1 for record in graded if record["grades"]["answer_token_f1"] is not None)
    truncation = sum(1 for record in graded if record["grades"]["truncated"])
    return {
        "fatal_count": fatal_count,
        "attempted_count": count,
        "text_responses_graded": text_available,
        "text_unavailable_count": count - text_available,
        "grades": {
            "recall_at_5": _mean_available(record["grades"]["recall_at_5"] for record in graded),
            "mrr": _mean_available(record["grades"]["mrr"] for record in graded),
            "citation_precision": _mean_available(record["grades"]["citation_precision"] for record in graded),
            "citation_validity_rate": _mean_available(record["grades"]["citation_validity_rate"] for record in graded),
            "task_resolution_rate": _mean_available(record["grades"]["task_resolution"] for record in graded),
            "answer_token_f1": _mean_available(record["grades"]["answer_token_f1"] for record in graded),
            "truncation_rate": truncation / count if count else 0.0,
        },
    }


def _answer_type_slices(graded: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-answer-type counts and token-F1 (text F1 skips malformed rows)."""
    by_type: dict[str, list[float | None]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for record in graded:
        answer_type = record["answer_type"]
        by_type[answer_type].append(record["grades"]["answer_token_f1"])
        counts[answer_type] += 1
    result: dict[str, Any] = {}
    for answer_type in sorted(counts):
        values = [value for value in by_type[answer_type] if value is not None]
        result[answer_type] = {
            "count": counts[answer_type],
            "answer_token_f1": sum(values) / len(values) if values else None,
        }
    return result


def _gate_inputs(aggregated: Mapping[str, Any], latency_report: Mapping[str, Any]) -> dict[str, float | int]:
    """The ten frozen promotion-gate inputs for one condition.

    Latency inputs (p95 TTFT/TTC) are taken from the T17 latency report rather
    than recomputed; local runtime serving cost is $0.00 (no external API).
    This function never decides C06 — it only assembles gate inputs.
    """
    p95 = latency_report["waterfalls"]["p95"]
    return {
        "fatal_count": aggregated["fatal_count"],
        "retrieval_recall_at_5": aggregated["grades"]["recall_at_5"],
        "citation_precision": aggregated["grades"]["citation_precision"],
        "citation_validity_rate": aggregated["grades"]["citation_validity_rate"],
        "task_resolution_rate": aggregated["grades"]["task_resolution_rate"],
        "answer_token_f1": aggregated["grades"]["answer_token_f1"],
        "truncation_rate": aggregated["grades"]["truncation_rate"],
        "p95_ttft_ms": p95["ttft_ms"],
        "p95_ttc_ms": p95["ttc_ms"],
        "external_runtime_api_cost_per_completed_task": FROZEN_THRESHOLDS["external_runtime_api_cost_per_completed_task"],
    }


def _answer_type_deltas_vs_b0(
    slices_by_condition: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Per-answer-type token-F1 delta of each intervention versus B0."""
    baseline = slices_by_condition["B0_buffered_256"]
    deltas: dict[str, Any] = {}
    for condition in ("I1_streaming_256", "I2_buffered_128"):
        candidate = slices_by_condition[condition]
        delta: dict[str, float | None] = {}
        for answer_type in sorted(set(baseline) | set(candidate)):
            base_f1 = baseline.get(answer_type, {}).get("answer_token_f1")
            cand_f1 = candidate.get(answer_type, {}).get("answer_token_f1")
            if base_f1 is None or cand_f1 is None:
                delta[answer_type] = None
            else:
                delta[answer_type] = cand_f1 - base_f1
        deltas[condition] = delta
    return deltas


def _build_t18(
    traces: Sequence[Mapping[str, Any]],
    cases_by_id: Mapping[str, Mapping[str, Any]],
    holdout_ids: set[str],
    latency_reports: Mapping[str, Mapping[str, Any]],
    run_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    graded: list[dict[str, Any]] = []
    for trace in traces:
        case = cases_by_id.get(str(trace["case_id"]), {})
        fatal, answer_text, recomputed_citations = _recompute_validation (trace)
        # Only trust recomputed citations for rows the run-time validator wrongly 
        # rejected (e.g. a boolean answer): their persisted scores.citation_ids is 
        # empty. Rows that already validated keep their run-time citation ids.
        reclassified = bool(trace.get("fatal_gates")) and not fatal
        graded.append({
            "trace_id": str(trace["trace_id"]),
            "case_id": str(trace["case_id"]),
            "condition_id": str(trace["condition_id"]),
            "repetition": trace["repetition"],
            "answer_type": str(trace.get("answer_type", "")),
            "fatal": fatal,
            "grades": _grade_attempt(
            trace, case, answer_text,
            citation_override=recomputed_citations if reclassified else None,
            ),
        })

    by_condition: dict[str, Any] = {}
    slices_by_condition: dict[str, Any] = {}
    for condition in REGISTERED_CONDITIONS:
        cond_graded = [record for record in graded if record["condition_id"] == condition]
        aggregated = _aggregate_grades(cond_graded)
        slices = _answer_type_slices(cond_graded)
        by_condition[condition] = {
            **aggregated,
            "answer_type_slices": slices,
            "frozen_gate_inputs": _gate_inputs(aggregated, latency_reports[condition]),
        }
        slices_by_condition[condition] = slices

    # Repetition-zero one record per case x condition (24 x 3 = 72).
    rep_zero = sorted(
        (
            {
                "case_id": record["case_id"],
                "condition_id": record["condition_id"],
                "repetition": record["repetition"],
                "trace_id": record["trace_id"],
                "fatal": record["fatal"],
                "grades": record["grades"],
            }
            for record in graded
            if record["repetition"] == 0
        ),
        key=lambda record: (record["condition_id"], record["case_id"]),
    )

    # Five-rep parity: every case x condition pair must carry all 5 repetitions.
    pair_counts = Counter((record["case_id"], record["condition_id"]) for record in graded)
    rep_values = sorted({count for count in pair_counts.values()})
    parity_complete = len(rep_values) == 1 and rep_values and rep_values[0] == REPLICATION_COUNT

    holdout_overlap = sum(1 for trace in traces if str(trace["case_id"]) in holdout_ids)

    return {
        "schema": "offline-quality-evidence.v1",
        "contract_id": FROZEN_CONTRACT_ID,
        "run_id": run_manifest.get("run_id"),
        "condition_ids": list(REGISTERED_CONDITIONS),
        "grading_semantics": {
            "quality_metrics": "computed over all attempts per condition (retrieval/citation grades apply to malformed rows; text grades skip them)",
            "truncation_rate": "count(finish_reason == 'length') over all attempts per condition",
            "text_metrics": "None for malformed (non-string) answers; means skip None",
        },
        "parity": {
            "complete": parity_complete,
            "expected_replication": REPLICATION_COUNT,
            "observed_replication": rep_values[0] if len(rep_values) == 1 else rep_values,
            "case_condition_pairs": len(pair_counts),
        },
        "holdout_overlap_count": holdout_overlap,
        "rep_zero_grades": rep_zero,
        "by_condition": by_condition,
        "answer_type_deltas_vs_b0": _answer_type_deltas_vs_b0(slices_by_condition),
        "frozen_thresholds": dict(FROZEN_THRESHOLDS),
    }


# ---------------------------------------------------------------------------
# T19 provenance & budget evidence
# ---------------------------------------------------------------------------

def _nullable_metric(traces: Sequence[Mapping[str, Any]], field: str) -> dict[str, Any]:
    """Describe a nullable per-trace metric (input tokens / tokens-per-second)."""
    total = len(traces)
    values = [trace.get(field) for trace in traces]
    null_count = sum(1 for value in values if value is None)
    if null_count == total:
        reason = traces[0].get(f"{field}_reason") or "not_reported_by_model" if traces else "not_reported_by_model"
        return {"available": False, "null_count": null_count, "reason": reason}
    present = [float(value) for value in values if value is not None]
    return {
        "available": True,
        "null_count": null_count,
        "present_count": len(present),
        "mean": sum(present) / len(present) if present else None,
    }


def _tokens_evidence(traces: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output_tokens = [int(trace["output_tokens"]) for trace in traces if trace.get("output_tokens") is not None]
    completed = sum(1 for trace in traces if trace.get("error_type") is None)
    output_total = sum(output_tokens)
    return {
        "input_tokens": _nullable_metric(traces, "input_tokens"),
        "tokens_per_second": _nullable_metric(traces, "tokens_per_second"),
        "output_tokens_total": output_total,
        "output_tokens_per_completed_task": round(output_total / completed, 4) if completed else None,
        "completed_tasks": completed,
    }


def _budget_variance(
    latency_reports: Mapping[str, Mapping[str, Any]], budget: Mapping[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for condition, report in latency_reports.items():
        marginal = report["marginal_stages"]["stages"]
        p95 = report["waterfalls"]["p95"]
        stages: dict[str, Any] = {}
        for stage in TTC_STAGES:
            measured = float(marginal[f"{stage}_ms"]["p95"])
            budget_value = float(budget[stage])
            stages[stage] = {
                "measured_p95_ms": round(measured, 4),
                "budget_p95_ms": budget_value,
                "within_budget": measured <= budget_value,
            }
        ttc_measured = float(p95["ttc_ms"])
        ttc_entry = {
            "measured_p95_ms": round(ttc_measured, 4),
            "budget_p95_ms": float(budget["ttc"]),
            "within_budget": ttc_measured <= float(budget["ttc"]),
        }
        largest = max(stages, key=lambda stage: stages[stage]["measured_p95_ms"])
        result[condition] = {
            "stages": stages,
            "ttc": ttc_entry,
            "within_budget": all(entry["within_budget"] for entry in stages.values()) and ttc_entry["within_budget"],
            "largest_p95_stage": largest,
        }
    return result


def _interventions(
    latency_reports: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Per-condition p95 latency and intervention deltas versus the B0 baseline.

    ``perceived_latency_ms`` (first-token-displayed) is separated from
    ``total_latency_ms`` (TTC) — buffered mode displays only after validation,
    so its perceived latency equals TTC; streaming displays as soon as the first
    token arrives, decoupling perceived from total latency.
    """
    baseline = latency_reports["B0_buffered_256"]["waterfalls"]["p95"]
    result: dict[str, Any] = {
        "B0_buffered_256": {
            "ttc_p95_ms": round(float(baseline["ttc_ms"]), 4),
            "ttft_p95_ms": round(float(baseline["ttft_ms"]), 4),
            "first_token_displayed_p95_ms": round(float(baseline["first_token_displayed_ms"]), 4),
            "perceived_latency_ms": round(float(baseline["first_token_displayed_ms"]), 4),
            "total_latency_ms": round(float(baseline["ttc_ms"]), 4),
        }
    }
    for condition in ("I1_streaming_256", "I2_buffered_128"):
        p95 = latency_reports[condition]["waterfalls"]["p95"]
        result[condition] = {
            "ttc_p95_ms": round(float(p95["ttc_ms"]), 4),
            "ttft_p95_ms": round(float(p95["ttft_ms"]), 4),
            "first_token_displayed_p95_ms": round(float(p95["first_token_displayed_ms"]), 4),
            "perceived_latency_ms": round(float(p95["first_token_displayed_ms"]), 4),
            "total_latency_ms": round(float(p95["ttc_ms"]), 4),
            "ttc_delta_vs_b0_ms": round(float(p95["ttc_ms"]) - float(baseline["ttc_ms"]), 4),
            "first_token_displayed_delta_vs_b0_ms": round(
                float(p95["first_token_displayed_ms"]) - float(baseline["first_token_displayed_ms"]), 4
            ),
        }
    return result


def _environment(traces: Sequence[Mapping[str, Any]], run_manifest: Mapping[str, Any]) -> dict[str, Any]:
    first = traces[0]
    live = run_manifest.get("live_identity") or {}
    return {
        "python_version": first["python_version"],
        "macos_build": first["macos_build"],
        "chip": first["chip"],
        "ram_bytes": first["ram_bytes"],
        "power_mode": first["power_mode"],
        "ollama_version": first["ollama_version"],
        "model_tag": first["model_tag"],
        "model_digest": first["model_digest"],
        "dataset_repo": first["dataset_repo"],
        "dataset_revision": first["dataset_revision"],
        "corpus_hash": first["corpus_hash"],
        "index_snapshot": first["index_snapshot"],
        "live_identity": live,
        "thermal_observation": run_manifest.get("thermal_observation"),
        "swap_observation": run_manifest.get("swap_observation"),
    }


def _spend_evidence(thresholds: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "local_runtime_serving_cost": 0.0,
        "local_runtime_serving_cost_formatted": "$0.00",
        "external_runtime_api_cost_per_completed_task": FROZEN_THRESHOLDS[
            "external_runtime_api_cost_per_completed_task"
        ],
        "agent_spend": {
            "available": False,
            "reason": "no external API calls; runtime served qwen3:4b-instruct locally via Ollama",
        },
    }


def _build_t19(
    traces: Sequence[Mapping[str, Any]],
    run_manifest: Mapping[str, Any],
    latency_reports: Mapping[str, Mapping[str, Any]],
    thresholds: Mapping[str, Any],
    command: str,
) -> dict[str, Any]:
    budget = thresholds["latency_budget_p95_ms"]
    return {
        "schema": "offline-provenance-evidence.v1",
        "contract_id": FROZEN_CONTRACT_ID,
        "run_id": run_manifest.get("run_id"),
        "generation_command": command,
        "environment": _environment(traces, run_manifest),
        "tokens": _tokens_evidence(traces),
        "spend": _spend_evidence(thresholds),
        "budget": dict(budget),
        "budget_variance": _budget_variance(latency_reports, budget),
        "interventions": _interventions(latency_reports),
        "frozen_thresholds": dict(FROZEN_THRESHOLDS),
    }


def _render_t19_markdown(t19: Mapping[str, Any]) -> str:
    """Render the T19 Markdown evidence straight from the T19 JSON dict."""
    env = t19["environment"]
    tokens = t19["tokens"]
    spend = t19["spend"]
    lines: list[str] = [
        "# T19 Provenance & Budget Evidence",
        "",
        f"**Run:** `{t19['run_id']}`  ",
        f"**Contract:** `{t19['contract_id']}`  ",
        f"**Generated by:** `{t19['generation_command']}`",
        "",
        "## Environment",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Python | {env['python_version']} |",
        f"| macOS build | {env['macos_build']} |",
        f"| Chip | {env['chip']} |",
        f"| RAM (bytes) | {env['ram_bytes']} |",
        f"| Power mode | {env['power_mode']} |",
        f"| Ollama | {env['ollama_version']} |",
        f"| Model tag | {env['model_tag']} |",
        f"| Model digest | `{env['model_digest']}` |",
        f"| Corpus hash | `{env['corpus_hash']}` |",
        f"| Index snapshot | `{env['index_snapshot']}` |",
        "",
        "## Budget variance (p95 measured vs `latency_budget_p95_ms`)",
        "",
        "| Condition | Stage | Measured p95 (ms) | Budget p95 (ms) | Within budget |",
        "| --- | --- | --- | --- | --- |",
    ]
    for condition in REGISTERED_CONDITIONS:
        entry = t19["budget_variance"][condition]
        for stage, row in entry["stages"].items():
            lines.append(
                f"| {condition} | {stage} | {row['measured_p95_ms']} | "
                f"{row['budget_p95_ms']} | {row['within_budget']} |"
            )
        ttc_row = entry["ttc"]
        lines.append(
            f"| {condition} | ttc | {ttc_row['measured_p95_ms']} | "
            f"{ttc_row['budget_p95_ms']} | {ttc_row['within_budget']} |"
        )
    lines += ["", "## Interventions (vs B0_buffered_256)", "",
              "| Condition | TTC delta (ms) | First-token-displayed delta (ms) | Perceived (ms) | Total (ms) |",
              "| --- | --- | --- | --- | --- |"]
    for condition in REGISTERED_CONDITIONS:
        interv = t19["interventions"][condition]
        ttc_delta = interv.get("ttc_delta_vs_b0_ms", 0.0)
        ftd_delta = interv.get("first_token_displayed_delta_vs_b0_ms", None)
        lines.append(
            f"| {condition} | {ttc_delta} | {ftd_delta if ftd_delta is not None else '-'} | "
            f"{interv['perceived_latency_ms']} | {interv['total_latency_ms']} |"
        )
    lines += ["", "## Tokens", "",
              f"- input_tokens: {'unavailable (' + tokens['input_tokens'].get('reason', 'unavailable') + ')' if not tokens['input_tokens']['available'] else 'available'}",
              f"- tokens_per_second: {'unavailable (' + tokens['tokens_per_second'].get('reason', 'unavailable') + ')' if not tokens['tokens_per_second']['available'] else 'available'}",
              f"- output_tokens_total: {tokens['output_tokens_total']}",
              f"- output_tokens_per_completed_task: {tokens['output_tokens_per_completed_task']}",
              f"- completed_tasks: {tokens['completed_tasks']}",
              "", "## Spend", "",
              f"- local_runtime_serving_cost: {spend['local_runtime_serving_cost_formatted']}",
              f"- external_runtime_api_cost_per_completed_task: {spend['external_runtime_api_cost_per_completed_task']}",
              f"- agent_spend: unavailable ({spend['agent_spend']['reason']})",
              ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Charts (T17)
# ---------------------------------------------------------------------------

def _png_info(path: Path) -> dict[str, Any]:
    """Decode a PNG's signature, IHDR dimensions, and byte length without PIL."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ReportError(f"not a valid PNG file: {path}")
    # IHDR: width (bytes 16-20) and height (bytes 20-24), big-endian uint32.
    import struct as _struct
    width, height = _struct.unpack(">II", data[16:24])
    return {
        "signature": "89504e470d0a1a0a",
        "width": width,
        "height": height,
        "bytes": len(data),
    }


def _render_charts(
    output_dir: Path, latency_reports: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Render two deterministic PNGs from the generated latency JSON only.

    Returns metadata whose ``waterfall_values_by_condition`` stores the raw p50/p95
    TTC and first-token-displayed values taken straight from the latency reports,
    so tests can assert chart metadata equals the JSON source values exactly.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    conditions = list(REGISTERED_CONDITIONS)
    x = list(range(len(conditions)))

    # Snapshot the source p50/p95 values once (single source of truth).
    waterfall_values: dict[str, Any] = {}
    for condition in conditions:
        wf = latency_reports[condition]["waterfalls"]
        waterfall_values[condition] = {
            "p50_ttc_ms": wf["p50"]["ttc_ms"],
            "p95_ttc_ms": wf["p95"]["ttc_ms"],
            "p50_first_token_displayed_ms": wf["p50"]["first_token_displayed_ms"],
            "p95_first_token_displayed_ms": wf["p95"]["first_token_displayed_ms"],
        }

    # --- condition-latency.png: p50/p95 TTC and first-token-displayed per condition ---
    ttc_p50 = [waterfall_values[c]["p50_ttc_ms"] for c in conditions]
    ttc_p95 = [waterfall_values[c]["p95_ttc_ms"] for c in conditions]
    ftd_p50 = [waterfall_values[c]["p50_first_token_displayed_ms"] for c in conditions]
    ftd_p95 = [waterfall_values[c]["p95_first_token_displayed_ms"] for c in conditions]
    bar_width = 0.2
    offsets = [-1.5 * bar_width, -0.5 * bar_width, 0.5 * bar_width, 1.5 * bar_width]
    series = [
        ("p50 TTC", ttc_p50, offsets[0]),
        ("p95 TTC", ttc_p95, offsets[1]),
        ("p50 first-token-displayed", ftd_p50, offsets[2]),
        ("p95 first-token-displayed", ftd_p95, offsets[3]),
    ]
    fig, ax = plt.subplots(figsize=(10, 6))
    for label, values, offset in series:
        ax.bar([i + offset for i in x], values, bar_width, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, rotation=15, ha="right")
    ax.set_ylabel("latency (ms)")
    ax.set_title("p50/p95 TTC and first-token-displayed by condition")
    ax.legend()
    fig.tight_layout()
    cond_path = output_dir / "condition-latency.png"
    fig.savefig(cond_path, format="png", dpi=110)
    plt.close(fig)

    # --- waterfalls.png: stacked p50+p95 stage values per condition ---
    stage_fields = [f"{stage}_ms" for stage in TTC_STAGES]
    colors = plt.cm.tab10.colors
    fig, ax = plt.subplots(figsize=(10, 6))
    bar_width = 0.38
    bottoms_p50 = [0.0] * len(conditions)
    bottoms_p95 = [0.0] * len(conditions)
    for index, stage_field in enumerate(stage_fields):
        values_p50 = [latency_reports[c]["waterfalls"]["p50"][stage_field] for c in conditions]
        values_p95 = [latency_reports[c]["waterfalls"]["p95"][stage_field] for c in conditions]
        ax.bar(
            [i - bar_width / 2 for i in x], values_p50, bar_width,
            bottom=bottoms_p50, color=colors[index % len(colors)],
            label=TTC_STAGES[index] if index < 6 else None,
        )
        ax.bar(
            [i + bar_width / 2 for i in x], values_p95, bar_width,
            bottom=bottoms_p95, color=colors[index % len(colors)],
            hatch="//",
            label=None,
        )
        bottoms_p50 = [b + v for b, v in zip(bottoms_p50, values_p50)]
        bottoms_p95 = [b + v for b, v in zip(bottoms_p95, values_p95)]
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, rotation=15, ha="right")
    ax.set_ylabel("latency (ms)")
    ax.set_title("Aligned p50 (solid) and p95 (hatched) stage waterfalls")
    ax.legend(loc="upper right", fontsize="small")
    fig.tight_layout()
    waterfalls_path = output_dir / "waterfalls.png"
    fig.savefig(waterfalls_path, format="png", dpi=110)
    plt.close(fig)

    return {
        "condition_latency_png": {"name": cond_path.name, **_png_info(cond_path)},
        "waterfalls_png": {"name": waterfalls_path.name, **_png_info(waterfalls_path)},
        "waterfall_values_by_condition": waterfall_values,
    }


# ---------------------------------------------------------------------------
# Top-level report generation
# ---------------------------------------------------------------------------

def generate_reports(
    *,
    run_dir: Path,
    output_dir: Path,
    cases_path: Path = DEFAULT_CASES,
    holdout_manifest_path: Path = DEFAULT_HOLDOUT,
    thresholds_path: Path = DEFAULT_THRESHOLDS,
    seed: int = SEED,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, object]:
    """Validate a frozen T16 run and emit reproducible T17/T18/T19 evidence.

    Loads verified inputs from ``run_dir``, emits one latency JSON per registered
    condition plus the T18 quality evidence, T19 provenance evidence, charts,
    and a machine-readable manifest that hashes every input and output.
    """
    _require_empty_output(output_dir)
    traces, run_manifest = _load_and_validate_run(run_dir)
    cases_by_id = _load_cases(cases_path)
    holdout_ids = _load_holdout_ids(holdout_manifest_path)
    _check_holdout_overlap(traces, holdout_ids)
    thresholds = _load_thresholds(thresholds_path)

    command = f".venv/bin/python -m scripts.reporting --run-dir {run_dir} --output-dir {output_dir}"

    # T17 — per-condition latency reports (returned dicts feed T18/T19).
    latency_reports: dict[str, dict[str, Any]] = {}
    for condition_id in REGISTERED_CONDITIONS:
        report = write_condition_report(
            traces=traces,
            condition_id=condition_id,
            output_path=output_dir / f"latency.{condition_id}.json",
            bootstrap_seed=seed,
            bootstrap_resamples=bootstrap_resamples,
            cases_by_id=cases_by_id,
            command=command,
        )
        latency_reports[condition_id] = report

    # T18 — quality evidence (gate inputs only; does not decide C06).
    t18 = _build_t18(traces, cases_by_id, holdout_ids, latency_reports, run_manifest)
    (output_dir / T18_NAME).write_text(
        json.dumps(t18, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    # T19 — provenance, tokens, spend, budget variance, interventions.
    t19 = _build_t19(traces, run_manifest, latency_reports, thresholds, command)
    (output_dir / T19_JSON_NAME).write_text(
        json.dumps(t19, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / T19_MD_NAME).write_text(_render_t19_markdown(t19), encoding="utf-8")

    # T17 (charts) — rendered from latency JSON only, hashed into the manifest.
    chart_metadata = _render_charts(output_dir, latency_reports)

    manifest = _build_manifest(
        run_dir=run_dir, output_dir=output_dir, run_manifest=run_manifest,
        cases_path=cases_path, holdout_manifest_path=holdout_manifest_path,
        thresholds_path=thresholds_path, command=command, seed=seed,
        bootstrap_resamples=bootstrap_resamples, traces=traces,
        chart_metadata=chart_metadata,
    )
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--holdout-manifest", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    args = parser.parse_args(argv)
    try:
        manifest = generate_reports(
            run_dir=args.run_dir, output_dir=args.output_dir,
            cases_path=args.cases, holdout_manifest_path=args.holdout_manifest,
            thresholds_path=args.thresholds, seed=args.seed,
            bootstrap_resamples=args.resamples,
        )
    except ReportError as exc:
        print(f"reporting blocked: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {len(manifest['output_hashes'])} reports to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
