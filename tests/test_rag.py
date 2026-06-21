"""Tests for grounded RAG generation + default-deny (backend & retriever mocked)."""

from __future__ import annotations

from collections.abc import Sequence

from maayan.generate.base import Message
from maayan.generate.rag import RAGService, build_context, extract_cited_refs
from maayan.retrieve.models import RetrievalResult, SearchResult


class FakeRetriever:
    """Returns a fixed RetrievalResult; records nothing."""

    def __init__(self, results: list[SearchResult], relevance: float) -> None:
        self._result = RetrievalResult(results=results, relevance=relevance)

    def retrieve(self, query: str, *, k=None, book=None, source=None) -> RetrievalResult:
        return self._result


class RecordingBackend:
    """Records calls and returns a canned completion."""

    def __init__(self, reply: str = "Answer grounded in [S1].") -> None:
        self.reply = reply
        self.calls: list[tuple[str, list[Message]]] = []

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        return self.reply


def _result(ref: str, text: str, score: float = 0.5, source: str = "sefaria") -> SearchResult:
    return SearchResult(
        ref=ref, text=text, score=score, lang="he", source=source, payload={"ref": ref}
    )


def test_empty_retrieval_refuses_without_calling_model() -> None:
    backend = RecordingBackend()
    rag = RAGService(FakeRetriever([], relevance=0.0), backend, score_threshold=0.4)
    answer = rag.ask("שאלה כלשהי")
    assert answer.grounded is False
    assert answer.cited_refs == []
    assert backend.calls == []  # default-deny: model never called


def test_below_threshold_refuses_without_calling_model() -> None:
    backend = RecordingBackend()
    results = [_result("Tanya 1:1", "טקסט כלשהו")]
    rag = RAGService(FakeRetriever(results, relevance=0.2), backend, score_threshold=0.4)
    answer = rag.ask("שאלה")
    assert answer.grounded is False
    assert backend.calls == []


def test_grounded_calls_backend_with_sources_in_context() -> None:
    backend = RecordingBackend(reply="כן, כפי שמבואר [S1].")
    results = [
        _result("Tanya, Part I; Likkutei Amarim 1:3", "בחירה חופשית"),
        _result("Tanya, Part I; Likkutei Amarim 2:1", "נפש אלוקית"),
    ]
    rag = RAGService(FakeRetriever(results, relevance=0.7), backend, score_threshold=0.4)
    answer = rag.ask("מהי בחירה חופשית")

    assert answer.grounded is True
    assert len(backend.calls) == 1
    _system, messages = backend.calls[0]
    user_content = messages[0].content
    # Both source refs and texts are present in the context handed to the model.
    assert "Tanya, Part I; Likkutei Amarim 1:3" in user_content
    assert "בחירה חופשית" in user_content
    assert "מהי בחירה חופשית" in user_content


def test_answer_surfaces_cited_refs() -> None:
    backend = RecordingBackend(reply="התשובה היא כך [S2], וגם [S1].")
    results = [
        _result("Tanya 1:3", "א"),
        _result("Tanya 2:1", "ב"),
    ]
    rag = RAGService(FakeRetriever(results, relevance=0.7), backend, score_threshold=0.4)
    answer = rag.ask("שאלה")
    assert answer.cited_refs == ["Tanya 2:1", "Tanya 1:3"]  # order of appearance


def test_extract_cited_refs_handles_tags_and_literals() -> None:
    sources = [_result("Tanya 1:1", "x"), _result("Tanya 1:2", "y")]
    assert extract_cited_refs("see [S1]", sources) == ["Tanya 1:1"]
    assert extract_cited_refs("as in Tanya 1:2", sources) == ["Tanya 1:2"]
    assert extract_cited_refs("none here", sources) == []


def test_build_context_numbers_sources() -> None:
    ctx = build_context([_result("Ref A", "alpha"), _result("Ref B", "beta")])
    assert "[S1] (Ref A) alpha" in ctx
    assert "[S2] (Ref B) beta" in ctx
