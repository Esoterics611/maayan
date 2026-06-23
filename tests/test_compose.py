"""Tests for Prompt 20 — brief → proposed outline (scaffolding; mock backend, no models)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import pytest

from maayan.clock import FakeClock
from maayan.compose.models import Brief, SourceScope
from maayan.compose.service import CompositionService, parse_outline
from maayan.compose.store import CompositionStore
from maayan.config import Settings
from maayan.generate.base import Message
from maayan.retrieve.models import RetrievalResult
from maayan.threads.service import ThreadService
from maayan.threads.store import ThreadStore


class _NullRetriever:
    """Outline tests never fill, so retrieval is never called."""

    def retrieve(self, query: str, *, k=None, book=None, source=None) -> RetrievalResult:
        return RetrievalResult(results=[], relevance=0.0)

OUTLINE = (
    "1. שתי הנפשות :: מהן הנפש האלוקית והבהמית\n"
    "2. בירור הנפש הבהמית :: כיצד מבררים את הנפש הבהמית\n"
    "3. אהבה בתענוגים :: מהי אהבה בתענוגים ומקורה"
)


class RecordingBackend:
    def __init__(self, reply: str = OUTLINE) -> None:
        self.reply = reply
        self.calls: list[tuple[str, list[Message]]] = []

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        return self.reply


class Harness(NamedTuple):
    svc: CompositionService
    store: CompositionStore
    threads: ThreadService
    backend: RecordingBackend
    settings: Settings


def _harness(backend: RecordingBackend | None = None, *, max_sections: int = 8,
             auto_outline: bool = False) -> Harness:
    backend = backend or RecordingBackend()
    store = CompositionStore(":memory:")
    threads = ThreadService(ThreadStore(":memory:"), FakeClock())
    settings = Settings(compose_max_sections=max_sections, compose_auto_outline=auto_outline)
    svc = CompositionService(_NullRetriever(), backend, store, threads, FakeClock(), settings)
    return Harness(svc, store, threads, backend, settings)


def _brief(**kw: object) -> Brief:
    base = dict(id="b-1", title="נפש הבהמית", intent="ללמד את בירור הנפש הבהמית",
                author="R. Ginsburgh")
    base.update(kw)
    return Brief(**base)  # type: ignore[arg-type]


# -- parse_outline: tolerant heading :: query parsing -------------------------
def test_parse_outline_extracts_heading_and_query() -> None:
    sections = parse_outline(OUTLINE)
    assert [s.heading for s in sections] == ["שתי הנפשות", "בירור הנפש הבהמית", "אהבה בתענוגים"]
    assert sections[0].query == "מהן הנפש האלוקית והבהמית"
    assert all(s.text == "" and s.supported is False for s in sections)  # structural, not filled


def test_parse_outline_falls_back_when_no_separator() -> None:
    sections = parse_outline("1. עיון בלי מפריד\n- שורה שניה")
    assert [s.heading for s in sections] == ["עיון בלי מפריד", "שורה שניה"]
    assert sections[0].query == sections[0].heading  # heading doubles as the query


# -- propose_outline ----------------------------------------------------------
def test_propose_outline_returns_sections_and_persists() -> None:
    h = _harness()
    comp = h.svc.propose_outline(_brief())

    assert comp.status == "proposed"
    assert [s.heading for s in comp.sections] == [
        "שתי הנפשות", "בירור הנפש הבהמית", "אהבה בתענוגים"
    ]
    assert comp.model == h.settings.generation_model
    # Round-trips through the store.
    loaded = h.store.get_composition(comp.id)
    assert loaded is not None and loaded.sections == comp.sections
    assert h.store.get_brief("b-1") is not None


def test_propose_outline_bounded_by_target_and_config() -> None:
    many = "\n".join(f"{i}. h{i} :: q{i}" for i in range(1, 13))  # 12 candidate sections
    # config cap 8, target 4 → the tighter (4) wins.
    h = _harness(RecordingBackend(many), max_sections=8)
    comp = h.svc.propose_outline(_brief(target_sections=4))
    assert len(comp.sections) == 4
    # config cap alone bounds it when no target is given.
    h2 = _harness(RecordingBackend(many), max_sections=5)
    assert len(h2.svc.propose_outline(_brief()).sections) == 5


def test_blank_author_is_rejected() -> None:
    with pytest.raises(ValueError, match="author is required"):
        _brief(author="   ")


def test_thread_brief_appends_a_composition_turn() -> None:
    h = _harness()
    thread = h.threads.start_thread("compose topic")
    comp = h.svc.propose_outline(_brief(thread_id=thread.id))

    turns = h.threads.get_thread_with_turns(thread.id).turns  # type: ignore[union-attr]
    assert turns[-1].turn_type == "composition"
    assert turns[-1].record_id == comp.id
    assert turns[-1].author == "R. Ginsburgh"


def test_source_scope_round_trips_on_the_brief() -> None:
    h = _harness()
    h.svc.propose_outline(_brief(source_scope=SourceScope(book="Tanya")))
    loaded = h.store.get_brief("b-1")
    assert loaded is not None and loaded.source_scope.book == "Tanya"


def test_outline_prompt_is_structural_not_cited() -> None:
    h = _harness()
    h.svc.propose_outline(_brief(seed_frameworks=["Sefer Yetzirah framework"]))
    system, messages = h.backend.calls[0]
    assert "Outline only" in system or "STRUCTURAL" in system
    # Seed frameworks are attributed in the prompt, never presented as citable sources.
    assert "Sefer Yetzirah framework" in messages[0].content
    assert "never cite" in messages[0].content
