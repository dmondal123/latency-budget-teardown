#!/usr/bin/env python3
"""Query a text-evidence manifest with fixed BM25 retrieval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from scripts.text_rag import TextRagError, assemble_context, build_index, retrieve


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    if not isinstance(manifest, dict):
        raise TextRagError("evidence manifest must be an object")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--retrieve-k", type=int, default=20)
    parser.add_argument("--admitted-top-k", type=int, default=5)
    parser.add_argument("--character-budget", type=int, default=12_000)
    args = parser.parse_args(argv)
    try:
        ranked = retrieve(build_index(load_manifest(args.manifest)), args.question, retrieve_k=args.retrieve_k)
        context = assemble_context(
            ranked, admitted_top_k=args.admitted_top_k, character_budget=args.character_budget
        )
    except (OSError, json.JSONDecodeError, TextRagError) as exc:
        print(f"retrieval blocked: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "ranked_evidence_ids": [item.evidence_id for item in ranked],
                "ranked_scores": [item.score for item in ranked],
                "admitted_evidence_ids": list(context.admitted_evidence_ids),
                "context": context.text,
                "abstained": context.abstained,
                "reason": context.reason,
                "input_characters": context.input_characters,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
