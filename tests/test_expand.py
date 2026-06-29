"""Tests for query expanders (lexicon deterministic; LLM via a fake backend)."""

from __future__ import annotations

from collections.abc import Sequence

from maayan.generate.base import Message
from maayan.lexicon.models import Term
from maayan.retrieve.expand import (
    CompositeExpander,
    ExpandedQuery,
    LexiconExpander,
    LLMQueryExpander,
    NullExpander,
)


class FakeTermSource:
    def __init__(self, terms: list[Term]) -> None:
        self._terms = terms

    def list_terms(self) -> list[Term]:
        return self._terms


class ScriptedBackend:
    """Returns queued replies in order; records the system prompts it was called with."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.systems: list[str] = []

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.systems.append(system)
        return self._replies.pop(0)


def _term(
    canonical: str,
    *,
    surface: list[str],
    related: list[str] | None = None,
    retracted: bool = False,
) -> Term:
    return Term(
        id=canonical,
        canonical=canonical,
        surface_forms=surface,
        definition="d",
        related_terms=related or [],
        author="tester",
        retracted=retracted,
    )


def test_null_expander_passes_through() -> None:
    assert NullExpander().expand("שאלה").queries == ["שאלה"]


def test_lexicon_expander_injects_matched_term_vocab() -> None:
    terms = FakeTermSource([
        _term('ע"ב (Name of 72 / Ab)', surface=['ע"ב'], related=['ס"ג', 'מ"ה']),
        _term("צמצום", surface=["צמצום"], related=["מקום פנוי"]),
    ])
    expanded = LexiconExpander(terms).expand('מהו ע"ב')
    assert expanded.queries[0] == 'מהו ע"ב'  # original first
    assert len(expanded.queries) == 2
    aug = expanded.queries[1]
    assert "Name of 72" in aug and 'ס"ג' in aug and 'מ"ה' in aug
    assert "מקום פנוי" not in aug  # the unmatched term contributes nothing


def test_lexicon_expander_no_match_is_passthrough() -> None:
    terms = FakeTermSource([_term("צמצום", surface=["צמצום"])])
    assert LexiconExpander(terms).expand("a question about prayer").queries == [
        "a question about prayer"
    ]


def test_lexicon_expander_skips_retracted_terms() -> None:
    terms = FakeTermSource([_term("צמצום", surface=["צמצום"], related=["x"], retracted=True)])
    assert LexiconExpander(terms).expand("מהו צמצום").queries == ["מהו צמצום"]


def test_llm_expander_parses_lines_and_appends_hyde() -> None:
    backend = ScriptedBackend([
        "1. first reformulation\n- second reformulation\n3) third\nfourth\nfifth",
        "A hypothetical source passage.",
    ])
    expanded = LLMQueryExpander(backend, variants=3, hyde=True).expand("the question")
    # original + 3 parsed variants (bullets stripped, capped at 3) + 1 HyDE passage
    assert expanded.queries == [
        "the question",
        "first reformulation",
        "second reformulation",
        "third",
        "A hypothetical source passage.",
    ]


def test_llm_expander_hyde_off_makes_one_call() -> None:
    backend = ScriptedBackend(["only one variant"])
    expanded = LLMQueryExpander(backend, variants=2, hyde=False).expand("q")
    assert expanded.queries == ["q", "only one variant"]
    assert len(backend.systems) == 1  # no HyDE call


def test_composite_dedupes_and_caps() -> None:
    class Echo:
        def __init__(self, extra: list[str]) -> None:
            self._extra = extra

        def expand(self, query: str) -> ExpandedQuery:
            return ExpandedQuery(original=query, queries=[query, *self._extra])

    comp = CompositeExpander(
        [Echo(["alpha", "beta"]), Echo(["beta", "gamma", "delta"])],
        max_queries=3,
    )
    out = comp.expand("orig").queries
    assert out[0] == "orig"  # original always first
    assert out == ["orig", "alpha", "beta"]  # deduped (beta once) and capped at 3
