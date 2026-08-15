#!/usr/bin/env python3
"""Create a deterministic, content-addressed page evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ingest(corpus: Path, output: Path) -> dict[str, object]:
    pdfs = sorted(corpus.glob("*.pdf"), key=lambda p: p.name.casefold())
    documents: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    for pdf in pdfs:
        raw = pdf.read_bytes()
        document_sha = _sha256(raw)
        with fitz.open(stream=raw, filetype="pdf") as doc:
            pages = []
            for page_number, page in enumerate(doc, start=1):
                text = page.get_text("text", sort=True).replace("\r\n", "\n").replace("\r", "\n").strip()
                text_bytes = text.encode("utf-8")
                evidence_id = f"{document_sha[:16]}:p{page_number}"
                record = {
                    "evidence_id": evidence_id,
                    "document_name": pdf.name,
                    "document_sha256": document_sha,
                    "page": page_number,
                    "page_count": len(doc),
                    "text": text,
                    "text_sha256": _sha256(text_bytes),
                    "source": {"path": pdf.name, "page": page_number},
                }
                evidence.append(record)
                pages.append({"page": page_number, "evidence_id": evidence_id, "text_sha256": record["text_sha256"]})
        documents.append({"document_name": pdf.name, "document_sha256": document_sha, "page_count": len(pages), "pages": pages})
    manifest = {"schema_version": "evidence-manifest.v1", "corpus": corpus.name, "documents": documents, "evidence": evidence}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("documents"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence_manifest.v1.json"))
    args = parser.parse_args()
    manifest = ingest(args.corpus, args.output)
    print(f"ingested {len(manifest['documents'])} PDFs and {len(manifest['evidence'])} pages -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
