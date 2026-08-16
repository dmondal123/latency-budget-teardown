#!/usr/bin/env python3
"""Materialize the pinned text-RAG dataset with reproducible identity records.

The Hugging Face cache is deliberately kept outside the repository.  The
manifest records absolute cache paths and hashes so a later run can verify the
same downloaded inputs without committing the cache itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


DATASET_REPOSITORY = "rag-datasets/rag-mini-wikipedia"
DATASET_REVISION = "1f9f3b53fbc5995b85aab8e993504ad42c5f16f6"
CONFIGURATIONS = (
    {"config": "text-corpus", "split": "passages", "schema": {"id": "integer", "passage": "string"}},
    {"config": "question-answer", "split": "test", "schema": {"id": "integer", "question": "string", "answer": "string"}},
)
_WHITESPACE = re.compile(r"\s+")


class MaterializationError(RuntimeError):
    """A deterministic, user-actionable materialization failure."""


@dataclass(frozen=True)
class LoadedRows:
    rows: tuple[dict[str, Any], ...]
    columns: tuple[str, ...]
    downloaded_files: tuple[Path, ...]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(value: str) -> str:
    """Normalize Unicode and whitespace without changing word content."""

    if not isinstance(value, str):
        raise MaterializationError(f"expected text, got {type(value).__name__}")
    value = unicodedata.normalize("NFKC", value)
    return _WHITESPACE.sub(" ", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _validate_row(row: dict[str, Any], schema: dict[str, str], row_number: int) -> None:
    missing = sorted(set(schema) - set(row))
    if missing:
        raise MaterializationError(f"row {row_number} is missing required columns: {missing}")
    identifier = row["id"]
    if isinstance(identifier, bool) or not isinstance(identifier, int):
        raise MaterializationError(f"row {row_number} id must be an integer")
    for column, kind in schema.items():
        if column == "id":
            continue
        if not isinstance(row[column], str):
            raise MaterializationError(f"row {row_number} {column} must be a string")


def normalized_corpus_hash(rows: Iterable[dict[str, Any]], schema: dict[str, str]) -> tuple[str, int]:
    """Hash canonical rows sorted by integer ID; return hash and row count."""

    materialized = [dict(row) for row in rows]
    for number, row in enumerate(materialized):
        _validate_row(row, schema, number)
    materialized.sort(key=lambda row: row["id"])
    ids = [row["id"] for row in materialized]
    if len(ids) != len(set(ids)):
        raise MaterializationError("dataset contains duplicate row IDs")
    lines = []
    for row in materialized:
        canonical = {"id": row["id"]}
        for column in schema:
            if column != "id":
                canonical[column] = normalize_text(row[column])
        lines.append(json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return sha256_bytes(("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")), len(materialized)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _cache_files(cache_dir: Path) -> tuple[Path, ...]:
    if not cache_dir.exists():
        return ()
    return tuple(sorted((p.resolve() for p in cache_dir.rglob("*") if p.is_file() and not p.name.endswith(".lock")), key=str))


def load_huggingface(config: str, split: str, cache_dir: Path, revision: str) -> LoadedRows:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise MaterializationError(
            "datasets tooling is unavailable; install requirements.txt (or run in the Python 3.12 environment)"
        ) from exc
    try:
        dataset = load_dataset(DATASET_REPOSITORY, config, split=split, revision=revision, cache_dir=str(cache_dir))
    except Exception as exc:  # datasets exposes several version-specific exception types
        raise MaterializationError(f"failed to load {config}/{split} at revision {revision}: {exc}") from exc
    columns = tuple(str(column) for column in dataset.column_names)
    rows = tuple(dict(row) for row in dataset)
    return LoadedRows(rows=rows, columns=columns, downloaded_files=_cache_files(cache_dir))


def materialize(
    *,
    cache_root: Path,
    loader: Callable[[str, str, Path, str], LoadedRows] = load_huggingface,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    repo_root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    cache_root = cache_root.expanduser().resolve()
    if _inside(cache_root, repo_root):
        raise MaterializationError(f"dataset cache must be outside repository: {cache_root}")
    cache_root.mkdir(parents=True, exist_ok=True)
    configurations: list[dict[str, Any]] = []
    overall_status = "materialized"
    for expected in CONFIGURATIONS:
        config = expected["config"]
        split = expected["split"]
        record: dict[str, Any] = {
            "config": config,
            "split": split,
            "source_revision": DATASET_REVISION,
            "expected_schema": expected["schema"],
            "status": "pending",
            "columns": None,
            "row_count": None,
            "downloaded_files": [],
            "normalized_corpus_sha256": None,
            "error": None,
        }
        try:
            loaded = loader(config, split, cache_root / config, DATASET_REVISION)
            missing_columns = sorted(set(expected["schema"]) - set(loaded.columns))
            unexpected_columns = sorted(set(loaded.columns) - set(expected["schema"]))
            if missing_columns or unexpected_columns:
                raise MaterializationError(
                    f"schema mismatch; missing columns: {missing_columns}; unexpected columns: {unexpected_columns}"
                )
            corpus_hash, row_count = normalized_corpus_hash(loaded.rows, expected["schema"])
            record.update(
                {
                    "status": "materialized",
                    "columns": list(loaded.columns),
                    "row_count": row_count,
                    "downloaded_files": [
                        {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
                        for path in loaded.downloaded_files
                    ],
                    "normalized_corpus_sha256": corpus_hash,
                }
            )
        except MaterializationError as exc:
            overall_status = "blocked"
            record["status"] = "blocked"
            record["error"] = str(exc)
        configurations.append(record)
    return {
        "schema_version": "dataset-materialization.v1",
        "status": overall_status,
        "dataset": {"repository": DATASET_REPOSITORY, "revision": DATASET_REVISION, "license": "CC BY 3.0"},
        "cache_root": str(cache_root),
        "configurations": configurations,
        "normalized_corpus_hashes": {
            record["config"]: record["normalized_corpus_sha256"] for record in configurations
        },
    }


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_repo = Path(__file__).resolve().parents[1]
    parser.add_argument("--cache-root", type=Path, default=Path(os.environ.get("T06_DATASET_CACHE", Path.home() / ".cache" / "week-1-fde" / "datasets")))
    parser.add_argument("--output-root", type=Path, default=default_repo / "artifacts")
    parser.add_argument("--eval-manifest", type=Path, default=default_repo / "eval/v1/dataset_manifest.json")
    args = parser.parse_args(argv)
    try:
        manifest = materialize(cache_root=args.cache_root)
    except MaterializationError as exc:
        print(f"materialization blocked: {exc}", file=sys.stderr)
        return 2
    output = args.output_root / "dataset_materialization.v1.json"
    write_manifest(manifest, output)
    write_manifest(manifest, args.eval_manifest)
    print(f"{manifest['status']}: {output}")
    return 0 if manifest["status"] == "materialized" else 2


if __name__ == "__main__":
    raise SystemExit(main())
