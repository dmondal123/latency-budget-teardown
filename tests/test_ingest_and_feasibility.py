import json
from pathlib import Path

import fitz

from scripts.ingest_pdfs import ingest
from scripts.probe_feasibility import run_probes


def make_pdf(path: Path, pages: list[str]) -> None:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(path)


def test_ingestion_is_sorted_and_content_addressed(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    make_pdf(corpus / "b.pdf", ["second document"])
    make_pdf(corpus / "A.pdf", ["first page", "second page"])
    first = ingest(corpus, tmp_path / "one.json")
    second = ingest(corpus, tmp_path / "two.json")
    assert first == second
    assert [d["document_name"] for d in first["documents"]] == ["A.pdf", "b.pdf"]
    assert [e["page"] for e in first["evidence"]] == [1, 2, 1]
    assert all(len(e["document_sha256"]) == 64 for e in first["evidence"])
    assert first["evidence"][0]["text"] == "first page"


def test_feasibility_result_has_explicit_probe_statuses(tmp_path):
    manifest = {"target": {}, "runtime": {"server": "vllm-metal"}, "model": {"checkpoint": "candidate"}}
    result = run_probes(manifest, workdir=tmp_path)
    assert result["schema_version"] == "feasibility.v1"
    assert {p["name"] for p in result["probes"]} == {"text", "image", "memory", "swap", "prefix_cache", "multimodal_prefix_cache"}
    assert json.loads(json.dumps(result))["overall_status"] in {"pass", "fail"}
