"""Validate text-RAG fixtures without running or scoring a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator

from scripts.materialize_dataset import normalize_text


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_cases(cases: Sequence[Mapping[str, object]], holdout_manifest: Mapping[str, object], corpus_rows: Sequence[Mapping[str, object]]) -> list[str]:
    errors: list[str] = []
    passages = {row.get("id"): normalize_text(str(row.get("passage", ""))).casefold() for row in corpus_rows}
    ids = [case.get("case_id") for case in cases]
    source_ids = [case.get("source_row_id") for case in cases]
    if len(ids) != len(set(ids)):
        errors.append("case IDs must be unique")
    if len(source_ids) != len(set(source_ids)):
        errors.append("source row IDs must be unique")
    expected_holdouts = {case.get("case_id") for case in cases if case.get("holdout") is True}
    if set(holdout_manifest.get("case_ids", [])) != expected_holdouts:
        errors.append("holdout manifest must name exactly the holdout cases")
    for case in cases:
        if case.get("verification_status") != "manually_verified":
            errors.append(f"{case.get('case_id')} is not manually verified")
        quote = case.get("support_quote")
        if not isinstance(quote, str) or not quote.strip():
            errors.append(f"{case.get('case_id')} has an empty support quote")
            continue
        normalized_quote = normalize_text(quote).casefold()
        for evidence_id in case.get("gold_evidence_ids", []):
            if evidence_id not in passages:
                errors.append(f"{case.get('case_id')} references missing passage {evidence_id}")
            elif normalized_quote not in passages[evidence_id]:
                errors.append(f"{case.get('case_id')} support quote is absent from passage {evidence_id}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--corpus-json", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    schema = _load(root / "eval/v1/case.schema.json")
    cases = _load(root / "eval/v1/development_cases.json") + _load(root / "eval/v1/holdout_cases.json")
    validator = Draft202012Validator(schema)
    errors = [f"{case.get('case_id', '<unknown>')}: {error.message}" for case in cases for error in validator.iter_errors(case)]
    errors.extend(validate_cases(cases, _load(root / "eval/v1/holdout_manifest.json"), _load(args.corpus_json)))
    if len(cases) != 30:
        errors.append(f"expected 30 cases, found {len(cases)}")
    if sum(case.get("holdout") is True for case in cases) != 6:
        errors.append("expected six sealed holdouts")
    if errors:
        print("verification failed:\n- " + "\n- ".join(errors))
        return 1
    print("validated 30 cases; sealed 6 holdouts; text-RAG fixtures are internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
