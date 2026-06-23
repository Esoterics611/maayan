"""Tests for Prompt 21 — per-section grounded fill (default-deny per section).

Mock retriever + backend; no network, no models.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

from maayan.clock import FakeClock
from maayan.compose.models import Brief, Composition, Section, SourceScope
from maayan.compose.service import CompositionService
from maayan.compose.store import CompositionStore
from maayan.config import Settings
from maayan.generate.base import Message
from maayan.retrieve.models import RetrievalResult, SearchResult
from maayan.threads.service import ThreadService
from maayan.threads.store import ThreadStore

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _sr(ref: str, text: str = "t") -> SearchResult:
    return SearchResult(ref=ref, text=text, score=0.6, lang="he", source="sefaria", payload={})


class FakeRetriever:
    def __init__(self, plan: dict[str, tuple[list[SearchResult], float]]) -> None:
        self._plan = plan
        self.calls: list[tuple[str, str | None, str | None]] = []

    def retrieve(self, query: str, *, k=None, book=None, source=None) -> RetrievalResult:
        self.calls.append((query, book, source))
        results, rel = self._plan.get(query, ([], 0.0))
        return RetrievalResult(results=results, relevance=rel)


class RecordingBackend:
    def __init__(self, section_reply: str = "נקודה מבוססת [S1].", outline: str = "") -> None:
        self.section_reply = section_reply
        self.outline = outline
        self.calls: list[tuple[str, list[Message]]] = []

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        return self.outline if "OUTLINE" in system else self.section_reply


class Harness(NamedTuple):
    svc: CompositionService
    store: CompositionStore
    retriever: FakeRetriever
    backend: RecordingBackend


def _harness(retriever: FakeRetriever, backend: RecordingBackend, *, threshold: float = 0.4,
             auto_outline: bool = False) -> Harness:
    store = CompositionStore(":memory:")
    threads = ThreadService(ThreadStore(":memory:"), FakeClock())
    settings = Settings(score_threshold=threshold, compose_section_top_k=5,
                        compose_auto_outline=auto_outline)
    svc = CompositionService(retriever, backend, store, threads, FakeClock(), settings)
    return Harness(svc, store, retriever, backend)


def _seed_brief(store: CompositionStore, **kw: object) -> Brief:
    base = dict(id="b-1", title="t", intent="i", author="A")
    base.update(kw)
    brief = Brief(**base)  # type: ignore[arg-type]
    store.save_brief(brief)
    return brief


def _seed_composition(store: CompositionStore, brief: Brief, queries: list[str]) -> Composition:
    comp = Composition(
        id="c-1", brief_id=brief.id, status="proposed", model="m", created_at=NOW,
        sections=[Section(heading=f"h{i}", query=q) for i, q in enumerate(queries, 1)],
    )
    store.save_composition(comp)
    return comp


# -- (a) below-threshold section => gap, no backend call ----------------------
def test_below_threshold_section_is_a_gap_with_no_model_call() -> None:
    retriever = FakeRetriever({"q-gap": ([_sr("Tanya 1:1")], 0.1)})  # below threshold
    backend = RecordingBackend()
    h = _harness(retriever, backend)
    brief = _seed_brief(h.store)
    _seed_composition(h.store, brief, ["q-gap"])

    filled = h.svc.fill("c-1")

    section = filled.sections[0]
    assert section.supported is False
    assert "honest gap" in section.text
    assert section.cited_refs == [] and section.grounded_in == []
    assert backend.calls == []  # default-deny: the model was never called for this section


def test_empty_retrieval_section_is_a_gap() -> None:
    h = _harness(FakeRetriever({"q": ([], 0.0)}), RecordingBackend())
    brief = _seed_brief(h.store)
    _seed_composition(h.store, brief, ["q"])
    assert h.svc.fill("c-1").sections[0].supported is False


# -- (b) supported section cites only retrieved refs --------------------------
def test_supported_section_cites_only_retrieved_refs() -> None:
    sources = [_sr("Tanya, Part I; Likkutei Amarim 1:6"), _sr("Torah Ohr, Bereshit 2:1")]
    retriever = FakeRetriever({"q-ok": (sources, 0.7)})
    backend = RecordingBackend(section_reply="כך מבואר [S1] וגם [S2].")
    h = _harness(retriever, backend)
    brief = _seed_brief(h.store)
    _seed_composition(h.store, brief, ["q-ok"])

    section = h.svc.fill("c-1").sections[0]

    assert section.supported is True
    assert section.cited_refs == [s.ref for s in sources]
    assert section.grounded_in == [s.ref for s in sources]
    assert backend.calls  # the model WAS called for a supported section


# -- (c) a mixed composition aggregates correctly -----------------------------
def test_mixed_composition_aggregates() -> None:
    retriever = FakeRetriever({
        "q-ok": ([_sr("Tanya 1:6")], 0.7),
        "q-gap": ([_sr("X")], 0.1),
    })
    backend = RecordingBackend(section_reply="מבוסס [S1].")
    h = _harness(retriever, backend)
    brief = _seed_brief(h.store)
    _seed_composition(h.store, brief, ["q-ok", "q-gap"])

    filled = h.svc.fill("c-1")

    assert [s.supported for s in filled.sections] == [True, False]
    assert filled.supported_sections == 1 and filled.gap_sections == 1
    assert filled.cited_refs == ["Tanya 1:6"]  # only the grounded section contributes
    assert filled.grounded_in == ["Tanya 1:6"]
    # Persisted.
    assert h.store.get_composition("c-1").gap_sections == 1  # type: ignore[union-attr]


# -- (d) seed_frameworks: attributed context, never cited ---------------------
def test_seed_frameworks_are_noncitable_context() -> None:
    retriever = FakeRetriever({"q": ([_sr("Tanya 1:6")], 0.7)})
    backend = RecordingBackend(section_reply="[S1]")
    h = _harness(retriever, backend)
    brief = _seed_brief(h.store, seed_frameworks=["Sefer Yetzirah lens"])
    _seed_composition(h.store, brief, ["q"])

    section = h.svc.fill("c-1").sections[0]

    _, messages = backend.calls[0]
    content = messages[0].content
    assert "Sefer Yetzirah lens" in content and "do NOT cite" in content
    assert "Sefer Yetzirah lens" not in section.cited_refs  # frameworks never cited


def test_source_scope_filters_pass_through_to_retriever() -> None:
    retriever = FakeRetriever({"q": ([_sr("Tanya 1:6")], 0.7)})
    h = _harness(retriever, RecordingBackend())
    brief = _seed_brief(h.store, source_scope=SourceScope(book="Tanya", source="sefaria"))
    _seed_composition(h.store, brief, ["q"])

    h.svc.fill("c-1")

    assert retriever.calls == [("q", "Tanya", "sefaria")]


# -- auto-outline fills immediately ------------------------------------------
def test_auto_outline_fills_right_after_propose() -> None:
    outline = "1. ראשון :: q1\n2. שני :: q2"
    retriever = FakeRetriever({"q1": ([_sr("Tanya 1:6")], 0.7), "q2": ([], 0.0)})
    backend = RecordingBackend(section_reply="[S1]", outline=outline)
    h = _harness(retriever, backend, auto_outline=True)

    comp = h.svc.propose_outline(Brief(id="b-1", title="t", intent="i", author="A"))

    # propose_outline returned an already-FILLED composition (one grounded, one gap).
    assert [s.supported for s in comp.sections] == [True, False]
    assert comp.cited_refs == ["Tanya 1:6"]


def test_fill_unknown_composition_raises() -> None:
    import pytest

    h = _harness(FakeRetriever({}), RecordingBackend())
    with pytest.raises(ValueError, match="not found"):
        h.svc.fill("nope")
