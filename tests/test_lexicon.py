"""Tests for the term lexicon: folding, protected expansion, store, convert, service."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from qdrant_client import QdrantClient

from maayan.clock import FakeClock
from maayan.corpus.models import Chunk
from maayan.corpus.normalize import expand_rashei_teivot, fold_surface
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.lexicon.convert import term_to_chunk
from maayan.lexicon.models import Term
from maayan.lexicon.service import TermService
from maayan.lexicon.store import TermStore
from maayan.retrieve.retriever import Retriever

DIM = 128


def _service() -> tuple[TermService, ChunkStore, QdrantIndex, HashingEmbedder]:
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    chunks = ChunkStore(":memory:")
    svc = TermService(TermStore(":memory:"), chunks, embedder, index, FakeClock())
    return svc, chunks, index, embedder


# -- folding + the protected-terms deny-list ---------------------------------

def test_fold_surface_is_gershayim_quote_nikkud_insensitive() -> None:
    assert fold_surface("ע״ב") == fold_surface('ע"ב') == fold_surface("עב")
    assert fold_surface("מָ״ה") == fold_surface("מה")  # nikkud + gershayim dropped
    assert fold_surface("  Ein  Sof ") == fold_surface("ein sof")  # ws + case


def test_protected_term_is_never_expanded() -> None:
    # An expansion table that would mangle ע"ב; the gershayim variant is protected.
    expansions = {'ע"ב': "WRONG-EXPANSION"}
    protected = frozenset({fold_surface("ע״ב")})  # registered as gershayim form
    text = 'כתוב ע"ב כאן'
    kept = expand_rashei_teivot(text, enabled=True, expansions=expansions, protected=protected)
    assert kept == text  # protected → untouched
    # Without protection, the same table WOULD expand it — proving the deny-list bites.
    expanded = expand_rashei_teivot(text, enabled=True, expansions=expansions)
    assert "WRONG-EXPANSION" in expanded


def test_blank_author_rejected() -> None:
    for bad in ("", "   "):
        with pytest.raises(ValidationError):
            Term(id="x", canonical="c", definition="d", author=bad)


# -- convert + store ----------------------------------------------------------

def test_term_to_chunk_carries_provenance_and_knowledge_only() -> None:
    term = Term(
        id="t1", canonical='ע"ב (Name of 72)', surface_forms=['ע"ב', "עב"],
        term_type="expansion", definition="the Ab expansion of Havayah, gematria 72",
        related_terms=['ס"ג', 'מ"ה', 'ב"ן'], gematria=72, sacred=True, author="R. Ginsburgh",
    )
    chunk = term_to_chunk(term)
    assert chunk.source == "term"
    assert term.definition in chunk.text and term.canonical in chunk.text
    meta = chunk.metadata
    assert meta["surface_forms"] == ['ע"ב', "עב"]
    assert meta["term_type"] == "expansion"
    assert meta["related_terms"] == ['ס"ג', 'מ"ה', 'ב"ן']
    assert meta["gematria"] == 72 and meta["sacred"] is True
    assert meta["author"] == "R. Ginsburgh" and meta["term_id"] == "t1"


def test_term_store_roundtrip_and_surface_form_lookup() -> None:
    store = TermStore(":memory:")
    store.create_term(Term(id="t1", canonical='ע"ב', surface_forms=['ע"ב'],
                           term_type="expansion", definition="d", gematria=72, author="A"))
    [reloaded] = store.list_terms()
    assert reloaded.gematria == 72 and reloaded.term_type == "expansion"
    # Lookup tolerates the gershayim variant and a no-quote variant.
    assert store.find_by_surface_form("ע״ב")[0].id == "t1"
    assert store.find_by_surface_form("עב")[0].id == "t1"
    assert store.find_by_surface_form("nope") == []


# -- service: index, retrieve, protected set, boost --------------------------

def test_add_term_is_indexed_retrievable_with_provenance() -> None:
    svc, chunks, index, embedder = _service()
    svc.add_term(
        canonical='ע"ב', surface_forms=['ע"ב'], term_type="expansion",
        definition="גילוי שם ע\"ב לאחר יחוד מ\"ה וב\"ן", author="R. Ginsburgh", gematria=72,
    )
    assert chunks.count(source="term") == 1
    assert chunks.count(only_unindexed=True) == 0
    results = Retriever(index, embedder, top_k=5).search("יחוד מה ובן")
    term_hits = [r for r in results if r.source == "term"]
    assert term_hits and term_hits[0].payload["metadata"]["author"] == "R. Ginsburgh"
    assert term_hits[0].payload["metadata"]["gematria"] == 72


def test_protected_terms_exposes_folded_surface_forms() -> None:
    svc, *_ = _service()
    svc.add_term(canonical='ע"ב', surface_forms=['ע"ב', "עב"], definition="d", author="A")
    protected = svc.protected_terms()
    assert fold_surface("ע״ב") in protected  # gershayim variant matches the registered form


def test_term_boost_changes_ranking() -> None:
    svc, chunks, index, embedder = _service()
    chunks.upsert_chunks([
        Chunk.make(ref="Tanya 1:1", book="Tanya", section_path=["1"], lang="he",
                   text="גילוי שם נרמז כאן", source="sefaria")
    ])
    index_chunks(store=chunks, embedder=embedder, index=index, batch_size=8)
    svc.add_term(canonical="גילוי שם", definition="גילוי שם נרמז כאן", author="A")

    boosted = Retriever(index, embedder, top_k=5, term_boost=8.0)
    top = boosted.search("גילוי שם נרמז")
    assert top[0].source == "term"  # the boost lifts the curated term to the top
