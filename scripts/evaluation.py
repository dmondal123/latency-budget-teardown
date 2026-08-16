"""Deterministic benchmark planning and offline reports from persisted trace JSONL."""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable, Mapping, Sequence

from .telemetry import TelemetryTrace


FROZEN_CONTRACT_ID = "text-rag-latency/v1"
FROZEN_THRESHOLD_DATE = "2026-08-16"
FROZEN_THRESHOLDS = {
    "fatal_count": 0,
    "retrieval_recall_at_5": 0.90,
    "citation_precision": 0.95,
    "citation_validity_rate": 0.98,
    "task_resolution_rate": 0.85,
    "answer_token_f1": 0.80,
    "truncation_rate_max": 0.02,
    "p95_ttft_ms": 3900,
    "p95_ttc_ms": 15000,
    "max_answer_type_slice_regression": 0.05,
    "external_runtime_api_cost_per_completed_task": 0.00,
}
REQUIRED_TRACE_FIELDS = TelemetryTrace.REQUIRED_FIELDS
CRITICAL_STAGES = tuple(f"{stage}_ms" for stage in TelemetryTrace.TTC_STAGES)

BASELINE_CONDITION = {
    "retriever": "bm25",
    "bm25_k1": 1.2,
    "bm25_b": 0.75,
    "retrieve_k": 20,
    "admitted_top_k": 5,
    "character_budget": 12_000,
    "max_tokens": 256,
    "stream_mode": False,
    "cache_state": "off",
    "keep_alive": "fixed",
    "think_mode": False,
    "temperature": 0,
    "retries": 0,
}
REGISTERED_CONDITIONS = {
    "B0_buffered_256": dict(BASELINE_CONDITION),
    "I1_streaming_256": {**BASELINE_CONDITION, "stream_mode": True},
    "I2_buffered_128": {**BASELINE_CONDITION, "max_tokens": 128},
}
REGISTERED_DELTAS = {
    "B0_buffered_256": frozenset(),
    "I1_streaming_256": frozenset({"stream_mode"}),
    "I2_buffered_128": frozenset({"max_tokens"}),
}


def _issue(category: str, **details: object) -> dict[str, object]:
    return {"category": category, **details}


def _nearest_rank(rows: Sequence[Mapping[str, Any]], field: str, percentile: int) -> Mapping[str, Any]:
    if not rows:
        raise ValueError("cannot select a percentile from no traces")
    ranked = sorted(rows, key=lambda row: (float(row[field]), str(row.get("trace_id", "")), str(row.get("case_id", ""))))
    rank = max(1, math.ceil(percentile / 100 * len(ranked)))
    return ranked[rank - 1]


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        raise ValueError("cannot average an empty collection")
    return sum(values) / len(values)


def assert_single_delta(
    condition_id: str, condition: Mapping[str, Any], *, baseline: Mapping[str, Any] = BASELINE_CONDITION
) -> None:
    """Reject any condition that changes undeclared or multiple baseline fields."""
    if condition_id not in REGISTERED_DELTAS:
        raise ValueError(f"unknown registered condition: {condition_id}")
    if set(condition) != set(baseline):
        raise ValueError("condition must contain exactly the baseline fields")
    changed = {field for field in baseline if condition[field] != baseline[field]}
    if changed != REGISTERED_DELTAS[condition_id]:
        raise ValueError(f"unregistered condition delta for {condition_id}: {sorted(changed)}")


def interleaved_schedule(
    *, case_ids: Sequence[str], condition_ids: Sequence[str], repetitions: int, seed: int
) -> list[dict[str, object]]:
    """Plan serial requests in seeded three-condition thermal blocks."""
    if not case_ids or not condition_ids or repetitions <= 0:
        raise ValueError("case_ids, condition_ids, and positive repetitions are required")
    for condition_id in condition_ids:
        assert_single_delta(condition_id, REGISTERED_CONDITIONS[condition_id])
    pairs = [(str(case_id), repetition) for repetition in range(repetitions) for case_id in case_ids]
    rng = random.Random(seed)
    rng.shuffle(pairs)
    schedule: list[dict[str, object]] = []
    for ordinal, (case_id, repetition) in enumerate(pairs, start=1):
        block_conditions = list(condition_ids)
        rng.shuffle(block_conditions)
        schedule.extend({
            "ordinal": (ordinal - 1) * len(block_conditions) + position,
            "thermal_block": ordinal,
            "case_id": case_id,
            "repetition": repetition,
            "condition_id": condition_id,
        } for position, condition_id in enumerate(block_conditions, start=1))
    return schedule


def run_conditions(
    *, case_ids: Sequence[str], condition_ids: Sequence[str], repetitions: int, seed: int,
    execute: Callable[[Mapping[str, object], Mapping[str, Any]], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Execute a previously interleaved matrix serially; measured failures are retained."""
    rows: list[dict[str, Any]] = []
    for scheduled in interleaved_schedule(
        case_ids=case_ids, condition_ids=condition_ids, repetitions=repetitions, seed=seed
    ):
        condition_id = str(scheduled["condition_id"])
        row = dict(execute(scheduled, REGISTERED_CONDITIONS[condition_id]))
        if row.get("condition_id") != condition_id:
            raise ValueError("executor returned a row for a different condition")
        rows.append(row)
    return rows


def validate_trace(trace: Mapping[str, Any]) -> list[dict[str, object]]:
    """Return machine-readable fatal/provenance problems without repairing the raw row."""
    issues: list[dict[str, object]] = []
    for field in REQUIRED_TRACE_FIELDS:
        # The raw schema intentionally contains nullable terminal/error fields
        # (for example TTA and error_type). Presence is the provenance contract;
        # values are interpreted according to their field-specific null reason.
        if field not in trace:
            issues.append(_issue("missing_required_field", field=field))
    if trace.get("error_type") is None:
        for field in (
            "raw_output", "retrieved_evidence_ids", "admitted_evidence_ids", "retrieved_ranks",
            "ttc_ms", "dataset_revision", "model_digest",
        ):
            if trace.get(field) is None:
                issues.append(_issue("missing_required_value", field=field))
    for stage in CRITICAL_STAGES:
        if trace.get(stage) is None:
            continue
        if not isinstance(trace[stage], (int, float)) or float(trace[stage]) < 0:
            issues.append(_issue("invalid_stage_duration", field=stage))
    if all(isinstance(trace.get(stage), (int, float)) for stage in CRITICAL_STAGES) and isinstance(trace.get("ttc_ms"), (int, float)):
        total = sum(float(trace[stage]) for stage in CRITICAL_STAGES)
        if not math.isclose(total, float(trace["ttc_ms"]), rel_tol=0, abs_tol=1e-6):
            issues.append(_issue("non_additive_ttc"))
    if trace.get("think_mode") is not False:
        issues.append(_issue("thinking_mode_enabled"))
    if trace.get("error_type") == "oom":
        issues.append(_issue("model_oom"))
    if trace.get("sustained_swap") is True:
        issues.append(_issue("sustained_swap"))
    fatal_gates = trace.get("fatal_gates", [])
    if not isinstance(fatal_gates, list):
        issues.append(_issue("malformed_output_or_citation_schema"))
    else:
        for gate in fatal_gates:
            issues.append(_issue(str(gate)))
    return issues


def enforce_sealed_holdout(*, phase: str, cases: Sequence[Mapping[str, Any]]) -> None:
    if phase != "holdout" and any(case.get("holdout") is True for case in cases):
        raise PermissionError("sealed holdout cases cannot be used before the holdout phase")


def select_frozen_cases(
    cases: Sequence[Mapping[str, Any]], *, seed: int, development_count: int, holdout_count: int
) -> dict[str, list[dict[str, Any]]]:
    """Select deterministic stratified development/holdout fixtures from reviewed cases."""
    if development_count + holdout_count > len(cases):
        raise ValueError("not enough cases for requested development and holdout splits")
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_type[str(case["answer_type"])].append(dict(case))
    rng = random.Random(seed)
    for values in by_type.values():
        values.sort(key=lambda case: str(case["case_id"]))
        rng.shuffle(values)
    types = sorted(by_type)
    selected: list[dict[str, Any]] = []
    while len(selected) < development_count + holdout_count:
        progressed = False
        for answer_type in types:
            if by_type[answer_type] and len(selected) < development_count + holdout_count:
                selected.append(by_type[answer_type].pop())
                progressed = True
        if not progressed:
            break
    development, holdout = selected[:development_count], selected[development_count:]
    for case in development:
        case["holdout"] = False
    for case in holdout:
        case["holdout"] = True
    return {"development": development, "holdout": holdout}


def grade_retrieval(*, retrieved_ids: Sequence[int], gold_ids: Sequence[int]) -> dict[str, float | int]:
    ranks = [position for position, evidence_id in enumerate(retrieved_ids, start=1) if evidence_id in set(gold_ids)]
    gold_rank = min(ranks) if ranks else 0
    return {
        "recall_at_1": float(gold_rank > 0 and gold_rank <= 1),
        "recall_at_3": float(gold_rank > 0 and gold_rank <= 3),
        "recall_at_5": float(gold_rank > 0 and gold_rank <= 5),
        "mrr": 1 / gold_rank if gold_rank else 0.0,
        "gold_rank": gold_rank,
    }


def grade_citations(*, cited_ids: Sequence[int], admitted_ids: Sequence[int], pinned_ids: Sequence[int]) -> dict[str, float]:
    cited = list(cited_ids)
    admissible = set(admitted_ids)
    pinned = set(pinned_ids)
    return {
        "citation_precision": _mean(float(value in admissible) for value in cited) if cited else 0.0,
        "citation_validity_rate": _mean(float(value in pinned) for value in cited) if cited else 0.0,
    }


def _normalized_tokens(text: object) ->list[str]:
    #Coerce non-string answers (e.g. a JSON boolean `true` for a yes/no
    # question) instead of raising, so a well-formed non-string answer is still
    # gradeable rather than silently dropped.

    return re.findall(r"[a-z0-9]+", str(text).casefold())

# Boolean questions have many equivalent correct surfaces ("Yes", "yes it is",
# JSON true). Grade them on polarity, not on string identity.

_BOOLEAN_TRUE_TOKENS = frozenset({"yes", "true", "correct", "affirmative"})
_BOOLEAN_FALSE_TOKENS = frozenset({"no", "false", "incorrect", "negative"})

def _boolean_polarity(tokens: Sequence [str]) -> bool | None:
    for token in tokens:
        if token in _BOOLEAN_TRUE_TOKENS:
            return True
        if token in _BOOLEAN_FALSE_TOKENS:
            return False
    return None


def _is_resolved(
    answer_tokens: Sequence [str], reference_tokens: Sequence [str], *, answer_type: str, exact: bool) -> bool:

    """Decide task resolution by content, not by exact string identity.
    Exact token equality (the previous definition) marked correct answers wrong whenever they differed only in verbosity: a fact stated inside a sentence ("...graduated in 1776" for the gold "1776") or a terse form of a verbose gold ("Lincoln" for "Lincoln was Roosevelt's presidential hero."). Booleans resolve on polarity; other answers resolve when the shorter normalized token set is fully contained in the longer. Genuinely different content ("Cairo" vs "Helsinki") shares no containment and stays unresolved, as does an answer that piles unsupported claims onto the gold fact.
    Known limits deterministic code cannot settle these, and a calibrated LLM judge is where they belong: morphological variants ("experimenting" vs "experiment") and pronoun substitutions ("his ancestry" vs "Wilson's ancestry") are not counted as matches.
    """

    if answer_type == "boolean":
        answer_polarity = _boolean_polarity(answer_tokens)
        reference_polarity = _boolean_polarity(reference_tokens)
        return answer_polarity is not None and answer_polarity == reference_polarity
    if exact:
        return True
    answer_set, reference_set = set(answer_tokens), set(reference_tokens)
    if not answer_set or not reference_set:
        return False
    return reference_set <= answer_set or answer_set <= reference_set


def grade_text_answer(*, answer: str, reference: str, answer_type: str, finish_reason: str | None) -> dict[str, float | bool]:
    full_answer_tokens, full_reference_tokens = _normalized_tokens (answer), _normalized_tokens (reference)
    # normalized_exact_match and answer_token_f1 keep their original definitions
    # (booleans compared on the leading token) so those reported metrics do not
    #move; only task_resolution changes to the content-based check below.

    answer_tokens, reference_tokens = _normalized_tokens(answer), _normalized_tokens(reference)
    if answer_type == "boolean":
        answer_tokens, reference_tokens = full_answer_tokens[:1], full_reference_tokens[:1]
    overlap = sum(min(answer_tokens.count(token), reference_tokens.count(token)) for token in set(answer_tokens))
    precision = overlap / len(answer_tokens) if answer_tokens else 0.0
    recall = overlap / len(reference_tokens) if reference_tokens else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    exact = float(answer_tokens == reference_tokens)
    return {
        "normalized_exact_match": exact,
        "answer_token_f1": f1,
        "task_resolution": float(
             _is_resolved(full_answer_tokens, full_reference_tokens, answer_type=answer_type, exact=bool(exact))
        ),
        "truncated": finish_reason == "length",
    }


def evaluate_promotion(
    metrics: Mapping[str, float | int], *, baseline_slices: Mapping[str, float], candidate_slices: Mapping[str, float]
) -> dict[str, object]:
    blockers: list[str] = []
    comparisons = (
        ("fatal_count", "eq", FROZEN_THRESHOLDS["fatal_count"]),
        ("retrieval_recall_at_5", "min", FROZEN_THRESHOLDS["retrieval_recall_at_5"]),
        ("citation_precision", "min", FROZEN_THRESHOLDS["citation_precision"]),
        ("citation_validity_rate", "min", FROZEN_THRESHOLDS["citation_validity_rate"]),
        ("task_resolution_rate", "min", FROZEN_THRESHOLDS["task_resolution_rate"]),
        ("answer_token_f1", "min", FROZEN_THRESHOLDS["answer_token_f1"]),
        ("truncation_rate", "max", FROZEN_THRESHOLDS["truncation_rate_max"]),
        ("p95_ttft_ms", "max", FROZEN_THRESHOLDS["p95_ttft_ms"]),
        ("p95_ttc_ms", "max", FROZEN_THRESHOLDS["p95_ttc_ms"]),
        ("external_runtime_api_cost_per_completed_task", "eq", FROZEN_THRESHOLDS["external_runtime_api_cost_per_completed_task"]),
    )
    for name, operation, threshold in comparisons:
        value = metrics.get(name)
        if value is None or (operation == "eq" and value != threshold) or (operation == "min" and value < threshold) or (operation == "max" and value > threshold):
            blockers.append(name)
    for answer_type, baseline_value in baseline_slices.items():
        if candidate_slices.get(answer_type, float("-inf")) < baseline_value - FROZEN_THRESHOLDS["max_answer_type_slice_regression"]:
            blockers.append("answer_type_slice_regression")
            break
    return {"accepted": not blockers, "blocking_categories": blockers}


def summarize_quality(rows: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    attempted = len(rows)
    valid = [row for row in rows if row.get("error_type") is None]
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("answer_type"))].append(row)
    return {
        "attempted_count": attempted,
        "valid_count": len(valid),
        "abstention_rate": _mean(float(bool(row.get("abstained"))) for row in rows) if rows else 0.0,
        "error_rate": _mean(float(row.get("error_type") is not None) for row in rows) if rows else 0.0,
        "by_answer_type": {name: {"count": len(values), "answer_token_f1": _mean(float(v.get("answer_token_f1", 0)) for v in values)} for name, values in sorted(grouped.items())},
        "quartiles": {"question_length": {}, "context_length": {}, "output_length": {}},
    }


def bootstrap_by_case(
    observations: Sequence[Mapping[str, Any]], *, metric: str, resamples: int, seed: int
) -> dict[str, object]:
    by_case: dict[str, list[float]] = defaultdict(list)
    for row in observations:
        by_case[str(row["case_id"])].append(float(row[metric]))
    if not by_case or resamples <= 0:
        raise ValueError("observations and positive resamples are required")
    cases = sorted(by_case)
    case_means = {case_id: _mean(by_case[case_id]) for case_id in cases}
    rng = random.Random(seed)
    samples = sorted(_mean(case_means[rng.choice(cases)] for _ in cases) for _ in range(resamples))
    return {
        "unit": "case", "case_count": len(cases), "repetition_count": len(observations), "seed": seed,
        "point_estimate": _mean(case_means.values()),
        "ci_low": samples[max(0, math.floor(0.025 * (resamples - 1)))],
        "ci_high": samples[min(resamples - 1, math.ceil(0.975 * (resamples - 1)))],
    }


def aligned_waterfalls(traces: Sequence[Mapping[str, Any]], *, stages: Sequence[str]) -> dict[str, dict[str, Any]]:
    complete = [trace for trace in traces if all(isinstance(trace.get(stage), (int, float)) for stage in stages) and isinstance(trace.get("ttc_ms"), (int, float))]
    result: dict[str, dict[str, Any]] = {}
    for percentile in (50, 95):
        selected = dict(_nearest_rank(complete, "ttc_ms", percentile))
        if not math.isclose(sum(float(selected[stage]) for stage in stages), float(selected["ttc_ms"]), abs_tol=1e-6):
            raise ValueError("waterfall stages must add to the selected trace TTC")
        result[f"p{percentile}"] = selected
    return result


def marginal_stage_percentiles(
    traces: Sequence[Mapping[str, Any]], *, stages: Sequence[str], seed: int, resamples: int
) -> dict[str, object]:
    table: dict[str, object] = {}
    for stage in stages:
        rows = [trace for trace in traces if isinstance(trace.get(stage), (int, float))]
        table[stage] = {
            "p50": float(_nearest_rank(rows, stage, 50)[stage]),
            "p95": float(_nearest_rank(rows, stage, 95)[stage]),
            **{key: value for key, value in bootstrap_by_case(rows, metric=stage, resamples=resamples, seed=seed).items() if key in {"ci_low", "ci_high"}},
        }
    return {"label": "marginal; columns are not additive", "bootstrap_unit": "case", "seed": seed, "stages": table}


def build_report_metadata(
    *, traces: Sequence[Mapping[str, Any]], condition_id: str, attempted_count: int, valid_count: int,
    bootstrap_seed: int, percentile_method: str, command: str,
) -> dict[str, object]:
    if not traces:
        raise ValueError("at least one trace is required for report metadata")
    first = traces[0]
    return {
        "run_ids": sorted({str(trace["run_id"]) for trace in traces}), "condition_id": condition_id,
        "attempted_count": attempted_count, "valid_count": valid_count,
        "dataset_repo": first["dataset_repo"], "dataset_revision": first["dataset_revision"],
        "corpus_hash": first["corpus_hash"], "index_snapshot": first["index_snapshot"],
        "model_tag": first["model_tag"], "model_digest": first["model_digest"],
        "environment": {key: first[key] for key in ("python_version", "macos_build", "chip", "ram_bytes", "power_mode", "ollama_version")},
        "contract_hash": first["contract_hash"], "bootstrap_seed": bootstrap_seed,
        "percentile_method": percentile_method, "generation_command": command,
    }


def _tail_trace(trace: Mapping[str, Any], cases_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Add report-only tail diagnostics from persisted trace and frozen case data."""
    enriched = dict(trace)
    case = cases_by_id.get(str(trace.get("case_id")), {})
    enriched["question_length"] = trace.get("question_length", len(str(case.get("question", ""))))
    enriched["context_length"] = trace.get("context_characters")
    ranks = trace.get("retrieved_ranks", {})
    gold_ids = case.get("gold_evidence_ids", [])
    if "gold_rank" not in enriched:
        if not case or not isinstance(gold_ids, Sequence) or not gold_ids:
            enriched["gold_rank"] = None
            enriched["gold_rank_reason"] = "unavailable_without_frozen_case"
        elif not isinstance(ranks, Mapping):
            enriched["gold_rank"] = None
            enriched["gold_rank_reason"] = "unavailable_without_retrieved_ranks"
        else:
            matched_ranks = [ranks.get(str(evidence_id)) for evidence_id in gold_ids]
            enriched["gold_rank"] = min((int(rank) for rank in matched_ranks if isinstance(rank, int)), default=0)
    enriched["truncated"] = trace.get("truncated", trace.get("finish_reason") == "length")
    return enriched


def tail_analysis(
    traces: Sequence[Mapping[str, Any]], *, stages: Sequence[str], percentile_method: str,
    cases_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, object]:
    cases = cases_by_id or {}
    enriched_traces = [_tail_trace(trace, cases) for trace in traces]
    threshold = float(_nearest_rank(enriched_traces, "ttc_ms", 90)["ttc_ms"])
    tail = [trace for trace in enriched_traces if float(trace["ttc_ms"]) >= threshold]
    median_trace = dict(_nearest_rank(enriched_traces, "ttc_ms", 50))
    def shares(row: Mapping[str, Any]) -> dict[str, float]:
        return {stage: float(row[stage]) / float(row["ttc_ms"]) for stage in stages}
    fields = {"answer_types": "answer_type", "question_lengths": "question_length", "context_lengths": "context_length", "output_lengths": "output_tokens", "gold_ranks": "gold_rank", "error_types": "error_type", "truncated": "truncated"}
    return {
        "tail_threshold_percentile": 90, "percentile_method": percentile_method, "tail_threshold_ttc_ms": threshold,
        "tail_traces": tail, "median_cohort_method": "nearest_rank", "median_cohort": median_trace,
        "tail_stage_shares": {stage: _mean(shares(trace)[stage] for trace in tail) for stage in stages},
        "median_stage_shares": shares(median_trace),
        "tail_diagnostics": {name: [trace.get(field) for trace in tail] for name, field in fields.items()},
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row {line_number} must be an object")
        rows.append(value)
    return rows


def write_condition_report(
    *, traces: Sequence[Mapping[str, Any]], condition_id: str, output_path: Path, bootstrap_seed: int,
    bootstrap_resamples: int, command: str, cases_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, object]:
    selected = [trace for trace in traces if trace.get("condition_id") == condition_id]
    if not selected:
        raise ValueError(f"no traces found for {condition_id}")
    valid = [trace for trace in selected if trace.get("error_type") is None and not validate_trace(trace)]
    report = {
        "metadata": build_report_metadata(traces=selected, condition_id=condition_id, attempted_count=len(selected), valid_count=len(valid), bootstrap_seed=bootstrap_seed, percentile_method="nearest empirical TTC-ranked trace", command=command),
        "waterfalls": aligned_waterfalls(valid, stages=CRITICAL_STAGES),
        "marginal_stages": marginal_stage_percentiles(valid, stages=CRITICAL_STAGES, seed=bootstrap_seed, resamples=bootstrap_resamples),
        "tail": tail_analysis(valid, stages=CRITICAL_STAGES, percentile_method="nearest_rank", cases_by_id=cases_by_id),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    report_parser = subparsers.add_parser("report", help="regenerate an offline condition report from raw JSONL")
    report_parser.add_argument("--input", required=True, type=Path)
    report_parser.add_argument("--output", required=True, type=Path)
    report_parser.add_argument("--condition", required=True, choices=sorted(REGISTERED_CONDITIONS))
    report_parser.add_argument("--cases", type=Path, default=Path("eval/v1/development_cases.json"))
    report_parser.add_argument("--seed", type=int, default=20260816)
    report_parser.add_argument("--resamples", type=int, default=10_000)
    args = parser.parse_args(argv)
    if args.command == "report":
        case_rows = json.loads(args.cases.read_text(encoding="utf-8"))
        if not isinstance(case_rows, list) or not all(isinstance(case, dict) for case in case_rows):
            raise ValueError("cases file must be a JSON array of objects")
        cases_by_id = {str(case["case_id"]): case for case in case_rows}
        write_condition_report(traces=load_jsonl(args.input), condition_id=args.condition, output_path=args.output, bootstrap_seed=args.seed, bootstrap_resamples=args.resamples, cases_by_id=cases_by_id, command=f"python -m scripts.evaluation report --input {args.input} --output {args.output} --condition {args.condition} --cases {args.cases} --seed {args.seed} --resamples {args.resamples}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
