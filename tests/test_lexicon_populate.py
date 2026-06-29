"""Tests for lexicon auto-population: mining, grounded drafting, expert-gate approval.

No network, no real models: the retriever and generation backend are fakes, the
embedder is the hashing stub, and Qdrant/SQLite run in memory.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from qdrant_client import QdrantClient

from maayan.clock import FakeClock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.embed.fake import HashingEmbedder
from maayan.generate.base import Message
from maayan.index.qdrant import QdrantIndex
from maayan.lexicon.populate import (
    SEED_TERMS,
    LexiconDrafter,
    LexiconPopulator,
    SeedTerm,
    TermSuggestion,
    mine_term_candidates,
)
from maayan.lexicon.service import TermService
from maayan.lexicon.store import TermStore
from maayan.lexicon.suggestions import SuggestionStore
from maayan.retrieve.models import RetrievalResult, SearchResult

DIM = 128


# -- fakes --------------------------------------------------------------------

class FakeRetriever:
    """Returns a fixed RetrievalResult regardless of the query."""

    def __init__(self, results: list[SearchResult], relevance: float) -> None:
        self._result = RetrievalResult(results=results, relevance=relevance)

    def retrieve(
        self, query: str, *, k: int | None = None, book: str | None = None,
        source: str | None = None,
    ) -> RetrievalResult:
        return self._result


class SequencedBackend:
    """Pops queued replies in order; records every call."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, list[Message]]] = []

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        return self._replies.pop(0)


def _src(ref: str, text: str, score: float = 0.6) -> SearchResult:
    return SearchResult(ref=ref, text=text, score=score, lang="he", source="sefaria",
                        payload={"ref": ref})


def _he(ref: str, text: str) -> Chunk:
    return Chunk.make(ref=ref, book="Tanya", section_path=["1"], lang="he", text=text)


# -- mining -------------------------------------------------------------------

def test_mine_groups_gershayim_variants_and_ranks_by_frequency() -> None:
    chunks = [
        _he("Tanya 1", 'ענין ע"ב וגם ע"ב נזכר כאן'),       # ע"ב (ASCII) x2
        _he("Tanya 2", 'שם ע״ב נרמז יחד עם חב"ד'),          # ע״ב (gershayim) x1, חב"ד x1
        Chunk.make(ref="En 1", book="Tanya", section_path=["1"], lang="en",
                   text='this "thing" is english'),         # english → ignored
    ]
    cands = mine_term_candidates(chunks, min_count=2, top_n=10)

    assert [c.folded for c in cands] == ["עב"]               # חב"ד (count 1) dropped by min_count
    top = cands[0]
    assert top.count == 3  # ASCII x2 + gershayim x1, folded as one
    assert top.surface == 'ע"ב'                              # most common raw spelling kept
    assert top.example_refs == ["Tanya 1", "Tanya 2"]


def test_mine_ignores_single_geresh_abbreviations() -> None:
    # וכו׳ ends in a single geresh with nothing after — not a term token.
    cands = mine_term_candidates([_he("T", "וכו׳ וכו׳ וכו׳")], min_count=1)
    assert cands == []


# -- drafter: grounding gate + faithfulness ----------------------------------

def _drafter(retriever: FakeRetriever, backend: SequencedBackend, *, verify: bool = True,
             threshold: float = 0.4) -> LexiconDrafter:
    return LexiconDrafter(retriever, backend, FakeClock(), model="fake-model",
                          top_k=4, score_threshold=threshold, verify=verify)


def test_ungrounded_term_is_unsupported_without_calling_model() -> None:
    backend = SequencedBackend(["should not be used"])
    drafter = _drafter(FakeRetriever([], relevance=0.0), backend)
    sug = drafter.draft(canonical='ע"ב', surface_forms=['ע"ב'])
    assert sug.supported is False
    assert sug.definition == "" and sug.source_refs == []
    assert backend.calls == []                              # nothing relevant → never drafts


def test_below_threshold_is_unsupported_without_calling_model() -> None:
    backend = SequencedBackend(["nope"])
    drafter = _drafter(FakeRetriever([_src("Tanya 1", "טקסט")], relevance=0.2), backend)
    sug = drafter.draft(canonical='ע"ב', surface_forms=['ע"ב'])
    assert sug.supported is False
    assert backend.calls == []


def test_insufficient_reply_is_unsupported() -> None:
    backend = SequencedBackend(["INSUFFICIENT"])
    drafter = _drafter(FakeRetriever([_src("Tanya 1", "טקסט")], relevance=0.7), backend)
    sug = drafter.draft(canonical='ע"ב', surface_forms=['ע"ב'])
    assert sug.supported is False
    assert sug.definition == "" and sug.source_refs == []
    assert len(backend.calls) == 1                          # drafted once, no verify after refusal


def test_supported_draft_cites_sources_and_passes_verify() -> None:
    backend = SequencedBackend(["שם ע\"ב הוא גילוי [S1].", "OK"])
    drafter = _drafter(FakeRetriever([_src("Tanya 1", "גילוי שם")], relevance=0.7), backend)
    sug = drafter.draft(
        canonical='ע"ב', surface_forms=['ע"ב'], term_type="expansion", origin="seed"
    )
    assert sug.supported is True
    assert sug.source_refs == ["Tanya 1"]
    assert sug.model == "fake-model" and sug.origin == "seed"
    assert len(backend.calls) == 2                          # draft + verify
    assert "TERM: ע\"ב" in backend.calls[0][1][0].content   # grounding prompt carries the term


def test_verify_flag_makes_draft_unsupported() -> None:
    backend = SequencedBackend(["טענה [S1].", "טענה [S1]."])  # verifier echoes one unsupported line
    drafter = _drafter(FakeRetriever([_src("Tanya 1", "טקסט")], relevance=0.7), backend)
    sug = drafter.draft(canonical='ע"ב', surface_forms=['ע"ב'])
    assert sug.supported is False
    assert sug.unsupported_claims == ["טענה [S1]."]


def test_uncited_draft_is_unsupported() -> None:
    # A definition with no [S#] tag isn't grounded even if the verifier says OK.
    backend = SequencedBackend(["הגדרה ללא ציטוט", "OK"])
    drafter = _drafter(FakeRetriever([_src("Tanya 1", "טקסט")], relevance=0.7), backend)
    sug = drafter.draft(canonical='ע"ב', surface_forms=['ע"ב'])
    assert sug.supported is False and sug.source_refs == []


# -- populator: queue + expert-gate approval ---------------------------------

def _populator(drafter: LexiconDrafter) -> tuple[LexiconPopulator, TermService]:
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    term_service = TermService(TermStore(":memory:"), ChunkStore(":memory:"),
                               embedder, index, FakeClock())
    pop = LexiconPopulator(drafter, SuggestionStore(":memory:"), term_service)
    return pop, term_service


def test_seed_suggestions_persist_only_supported() -> None:
    backend = SequencedBackend(["הגדרה [S1].", "OK"])
    drafter = _drafter(FakeRetriever([_src("Tanya 1", "גילוי שם")], relevance=0.7), backend)
    pop, _ = _populator(drafter)
    seed = SeedTerm(canonical='ע"ב', surface_forms=['ע"ב'], term_type="expansion")

    drafted = pop.suggest_from_seed([seed])
    assert len(drafted) == 1 and drafted[0].supported is True
    assert len(pop.list_pending()) == 1                      # supported draft queued for review


def test_approve_indexes_term_with_human_author() -> None:
    backend = SequencedBackend(["שם ע\"ב הוא גילוי [S1].", "OK"])
    drafter = _drafter(FakeRetriever([_src("Tanya 1", "גילוי שם")], relevance=0.7), backend)
    pop, term_service = _populator(drafter)

    [sug] = pop.suggest_from_seed([SeedTerm(canonical='ע"ב', surface_forms=['ע"ב'])])
    term = pop.approve(sug.id, author="R. Ginsburgh")

    assert term.author == "R. Ginsburgh"                    # author is the human approver
    assert term.source_refs == ["Tanya 1"]                  # corpus provenance carried through
    assert term_service.find_by_surface_form('ע"ב')         # now a real, retrievable term
    assert pop.list_pending() == []                         # left the queue


def test_approve_refuses_unsupported_suggestion() -> None:
    store = SuggestionStore(":memory:")
    backend = SequencedBackend([])  # never called
    drafter = _drafter(FakeRetriever([], relevance=0.0), backend)
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    term_service = TermService(TermStore(":memory:"), ChunkStore(":memory:"),
                               embedder, index, FakeClock())
    pop = LexiconPopulator(drafter, store, term_service)
    bad = store.create(TermSuggestion(id="x", canonical='ע"ב', supported=False,
                                      created_at=datetime(2026, 1, 1, tzinfo=UTC)))
    with pytest.raises(ValueError):
        pop.approve(bad.id, author="A")


def test_known_terms_are_skipped() -> None:
    backend = SequencedBackend(["הגדרה [S1].", "OK"])
    drafter = _drafter(FakeRetriever([_src("Tanya 1", "גילוי")], relevance=0.7), backend)
    pop, term_service = _populator(drafter)
    term_service.add_term(canonical='ע"ב', surface_forms=['ע"ב'], definition="d", author="A")

    drafted = pop.suggest_from_seed([SeedTerm(canonical='ע"ב', surface_forms=['ע"ב'])])
    assert drafted == []  # already in the lexicon → not re-drafted
    assert backend.calls == []


def test_seed_pack_is_nonempty_and_well_formed() -> None:
    assert len(SEED_TERMS) >= 20
    assert all(s.surface_forms for s in SEED_TERMS)
    assert any('ע"ב' in s.surface_forms for s in SEED_TERMS)


# -- suggestion store roundtrip ----------------------------------------------

def test_suggestion_store_roundtrip_and_status() -> None:
    store = SuggestionStore(":memory:")
    sug = TermSuggestion(
        id="s1", canonical='ע"ב', surface_forms=['ע"ב'], term_type="expansion",
        definition="d [S1]", source_refs=["Tanya 1"], supported=True, model="m",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    store.create(sug)
    [back] = store.list(status="pending")
    assert back.canonical == 'ע"ב' and back.source_refs == ["Tanya 1"] and back.supported is True
    store.set_status("s1", "approved")
    assert store.list(status="pending") == []
    assert store.count(status="approved") == 1
