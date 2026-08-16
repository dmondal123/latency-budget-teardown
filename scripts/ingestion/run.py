"""Create the durable text-passage manifest from the pinned HF cache."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .corpus import TextRagError, ingest_from_materialization, load_cached_passages, load_json, write_manifest
from .materialize import MaterializationError


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=Path(os.environ.get("T09_DATASET_CACHE", Path.home() / ".cache" / "week-1-fde" / "datasets")))
    parser.add_argument("--dataset-manifest", type=Path, default=repo_root / "artifacts/dataset_materialization.v1.json")
    parser.add_argument("--output", type=Path, default=repo_root / "artifacts/text_evidence_manifest.v1.json")
    args = parser.parse_args(argv)
    try:
        materialization = load_json(args.dataset_manifest)
        rows = load_cached_passages(args.cache_root / "text-corpus")
        manifest = ingest_from_materialization(rows, materialization)
        write_manifest(manifest, args.output)
    except (MaterializationError, TextRagError, OSError, json.JSONDecodeError) as exc:
        print(f"ingestion blocked: {exc}", file=sys.stderr)
        return 2
    print(f"ingested {len(manifest['passages'])} passages: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
