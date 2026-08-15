"""Task 6 retrieval and context-assembly contract tests.

The tests use the public ``scripts.retrieval`` API: manifest parsing into
page-level ``Evidence``, ``BM25.search``, the ``noop_reranker`` seam,
``assemble_context``, and ``bind_citations``.  The assertions encode the
ordering and hard-bound requirements in RAG_PIPELINE_PLAN.md 7.1-7.2.
"""

from copy import deepcopy

from scripts.retrieval import (
    BM25,
    assemble_context,
    bind_citations,
    evidence_from_manifest,
    noop_reranker,
    resolve_citations,
    retrieve_context,
)


def _record(
    evidence_id: str,
    document_name: str,
    page: int,
    text: str,
    *,
    title: str = "",
    adjacent: str = "",
    image: tuple[int, int] = (100, 100),
    render_sha256: str | None = None,
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "document_name": document_name,
        "document_sha256": f"{document_name}-sha",
        "page": page,
        "page_count": 4,
        "text": text,
        "visual_description": "",
        "text_sha256": f"text-{evidence_id}",
        "render_sha256": render_sha256 or f"render-{evidence_id}",
        "page_title": title,
        "adjacent_metadata": adjacent,
        "source": {"path": document_name, "page": page},
        "image_width": image[0],
        "image_height": image[1],
    }


def _evidence(*records: dict[str, object]):
    return evidence_from_manifest(
        {"schema_version": "evidence-manifest.v1", "evidence": list(records)}
    )


def test_bm25_ranking_and_ties_are_deterministic():
    evidence = _evidence(
        _record("z:p1", "z.pdf", 1, "latency latency"),
        _record("a:p1", "a.pdf", 1, "latency latency"),
        _record("m:p1", "m.pdf", 1, "budget only"),
    )

    first = BM25(evidence).search("latency", retrieve_k=3)
    second = BM25(evidence).search("latency", retrieve_k=3)

    assert [item.evidence.evidence_id for item in first] == ["a:p1", "z:p1"]
    assert first == second


def test_noop_reranker_is_an_explicit_order_preserving_seam():
    evidence = _evidence(_record("a:p1", "a.pdf", 1, "latency evidence"))
    candidates = BM25(evidence).search("latency", retrieve_k=1)

    ranked = noop_reranker("latency", candidates)

    assert ranked == candidates
    assert [item.rank for item in ranked] == [1]


def test_context_assembly_deduplicates_and_diversifies_with_document_cap():
    first = _record("a:p1", "a.pdf", 1, "alpha retrieval latency", render_sha256="same-render")
    duplicate = deepcopy(first)
    duplicate["evidence_id"] = "a:p3"
    second = _record("a:p2", "a.pdf", 2, "alpha retrieval latency details")
    other = _record("b:p1", "b.pdf", 1, "beta retrieval latency evidence")

    packed = assemble_context(
        "retrieval latency",
        _evidence(first, duplicate, second, other),
        reranker=noop_reranker,
        diversify_k=3,
        per_document_cap=1,
        token_budget=1_000,
        image_budget=2,
        pixel_budget=100_000,
    )

    assert [item.evidence_id for item in packed.evidence] == ["a:p1", "b:p1"]
    assert len({item.render_sha256 for item in packed.evidence}) == 2
    assert len({item.document_name for item in packed.evidence}) == 2


def test_lexical_mmr_prefers_a_new_document_before_a_redundant_page():
    packed = assemble_context(
        "retrieval latency",
        _evidence(
            _record("a:p1", "a.pdf", 1, "retrieval latency alpha"),
            _record("a:p2", "a.pdf", 2, "retrieval latency alpha details"),
            _record("b:p1", "b.pdf", 1, "retrieval latency beta rendering"),
        ),
        diversify_k=3,
        per_document_cap=2,
        token_budget=100,
        image_budget=3,
        pixel_budget=100_000,
        page_budget=3,
    )

    assert [item.evidence_id for item in packed.evidence] == ["a:p1", "b:p1", "a:p2"]


def test_metadata_expansion_is_limited_to_title_and_adjacent_structure():
    packed = assemble_context(
        "alpha",
        _evidence(_record("a:p1", "a.pdf", 1, "alpha evidence", title="Alpha", adjacent="Overview")),
        token_budget=100,
        image_budget=1,
        pixel_budget=10_000,
    )

    assert packed.evidence[0].page_title == "Alpha"
    assert packed.evidence[0].adjacent_metadata == "Alpha Overview"


def test_whole_page_pack_respects_token_image_and_pixel_bounds():
    evidence = _evidence(
        _record("a:p1", "a.pdf", 1, "one two three", image=(100, 100)),
        _record("b:p1", "b.pdf", 1, "four five six", image=(200, 100)),
    )

    packed = assemble_context(
        "one",
        evidence,
        token_budget=3,
        image_budget=1,
        pixel_budget=10_000,
    )

    assert [item.evidence_id for item in packed.evidence] == ["a:p1"]
    assert sum(len(item.text.split()) for item in packed.evidence) <= 3
    assert sum(1 for item in packed.evidence if item.pixels) <= 1
    assert sum(item.pixels for item in packed.evidence) <= 10_000
    assert packed.evidence[0].page == 1


def test_context_order_is_stable_even_when_manifest_input_order_changes():
    records = [
        _record("a:p1", "a.pdf", 1, "alpha retrieval latency"),
        _record("b:p1", "b.pdf", 1, "beta retrieval latency"),
    ]

    forward = assemble_context("retrieval latency", _evidence(*records), token_budget=100, image_budget=2, pixel_budget=100_000)
    reverse = assemble_context("retrieval latency", _evidence(*reversed(records)), token_budget=100, image_budget=2, pixel_budget=100_000)

    assert forward == reverse


def test_source_n_binds_only_admitted_evidence_and_resolves_durable_metadata():
    admitted = _evidence(
        _record("b:p1", "b.pdf", 1, "beta evidence"),
        _record("a:p1", "a.pdf", 1, "alpha evidence"),
    )

    bindings = bind_citations(admitted)

    assert [(binding.citation, binding.evidence_id) for binding in bindings] == [
        ("SOURCE_1", "a:p1"),
        ("SOURCE_2", "b:p1"),
    ]
    assert [dict(binding.source) for binding in bindings] == [
        {
            "path": "a.pdf",
            "page": 1,
            "document_name": "a.pdf",
            "document_sha256": "a.pdf-sha",
        },
        {
            "path": "b.pdf",
            "page": 1,
            "document_name": "b.pdf",
            "document_sha256": "b.pdf-sha",
        },
    ]
    assert resolve_citations(("SOURCE_2",), bindings)[0] == bindings[1]


def test_zero_admissible_evidence_abstains_before_model_dispatch():
    result = assemble_context("question with no matching evidence", (), token_budget=100)

    assert result.evidence == ()
    assert result.abstained is True
    assert result.reason == "zero_admissible_evidence"


def test_zero_evidence_does_not_dispatch_to_model():
    dispatched = []
    manifest = {"schema_version": "evidence-manifest.v1", "evidence": [_record("a:p1", "a.pdf", 1, "known fact")]}
    result = retrieve_context(manifest, "unmatched", model_dispatch=dispatched.append)
    assert result.abstained is True
    assert dispatched == []
