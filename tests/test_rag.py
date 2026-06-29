"""Tests for grounded RAG generation + default-deny (backend & retriever mocked)."""

from __future__ import annotations

from collections.abc import Sequence

from maayan.generate.base import Message
from maayan.generate.rag import ContextTurn, RAGService, build_context, extract_cited_refs
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


class SequencedBackend:
    """Returns queued replies in order (one per generate call); records every call."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, list[Message]]] = []

    @property
    def systems(self) -> list[str]:
        return [system for system, _ in self.calls]

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        return self._replies.pop(0)


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


def test_context_turns_appear_in_prompt_labeled_non_citable() -> None:
    backend = RecordingBackend(reply="grounded [S1].")
    results = [_result("Tanya, Part I; Likkutei Amarim 1:3", "נפש הבהמית")]
    rag = RAGService(FakeRetriever(results, relevance=0.7), backend, score_threshold=0.4)
    ctx = [ContextTurn(speaker="ask", text="Q: מהי נפש האלוקית\nA: היא חלק אלוק ממעל [S1]")]

    rag.ask("ונפש הבהמית?", context_turns=ctx)

    system, messages = backend.calls[0]
    content = messages[0].content
    assert "CONVERSATION SO FAR" in content
    assert "do NOT cite" in content
    assert "מהי נפש האלוקית" in content  # prior turn present so the follow-up resolves
    # Conversation block precedes the citable SOURCES block.
    assert content.index("CONVERSATION SO FAR") < content.index("SOURCES:")
    # The system prompt itself forbids citing the conversation.
    assert "Conversation so far" in system


def test_default_deny_holds_even_with_context_present() -> None:
    backend = RecordingBackend()
    rag = RAGService(FakeRetriever([], relevance=0.0), backend, score_threshold=0.4)
    answer = rag.ask("follow up", context_turns=[ContextTurn(speaker="ask", text="prior")])
    assert answer.grounded is False
    assert backend.calls == []  # context never bypasses default-deny


def test_only_retrieved_refs_are_cited_not_context_refs() -> None:
    # The model echoes a ref that exists ONLY in the conversation, plus a real [S1].
    backend = RecordingBackend(reply="As we saw at Tanya 99:9, and now [S1].")
    results = [_result("Tanya 1:3", "בחירה")]
    rag = RAGService(FakeRetriever(results, relevance=0.7), backend, score_threshold=0.4)
    ctx = [ContextTurn(speaker="ask", text="earlier: Tanya 99:9")]
    answer = rag.ask("q", context_turns=ctx)
    assert answer.cited_refs == ["Tanya 1:3"]  # the context-only ref is NOT cited


def test_extract_cited_refs_handles_tags_and_literals() -> None:
    sources = [_result("Tanya 1:1", "x"), _result("Tanya 1:2", "y")]
    assert extract_cited_refs("see [S1]", sources) == ["Tanya 1:1"]
    assert extract_cited_refs("as in Tanya 1:2", sources) == ["Tanya 1:2"]
    assert extract_cited_refs("none here", sources) == []


def test_build_context_numbers_sources() -> None:
    ctx = build_context([_result("Ref A", "alpha"), _result("Ref B", "beta")])
    assert "[S1] (Ref A) alpha" in ctx
    assert "[S2] (Ref B) beta" in ctx


# -- reasoning & synthesis (Prompt 31b) --------------------------------------

def test_reasoning_runs_analyze_then_synthesize() -> None:
    backend = SequencedBackend(["[S1] — core claim; agrees with [S2].", "Woven answer [S1][S2]."])
    results = [_result("Tanya 1:1", "א"), _result("Tanya 1:2", "ב")]
    rag = RAGService(
        FakeRetriever(results, relevance=0.7), backend, score_threshold=0.4, reasoning=True
    )
    answer = rag.ask("שאלה")

    assert len(backend.systems) == 2  # analyze, then synthesize
    assert "STUDY MAP" in backend.systems[0]  # stage 1 is the analyze prompt
    assert answer.reasoning == "[S1] — core claim; agrees with [S2]."
    assert answer.text == "Woven answer [S1][S2]."
    assert answer.cited_refs == ["Tanya 1:1", "Tanya 1:2"]


def test_synthesis_prompt_carries_study_map_and_sources() -> None:
    backend = SequencedBackend(["MAP: [S1] says X.", "answer [S1]."])
    results = [_result("Tanya 1:1", "טקסט")]
    rag = RAGService(
        FakeRetriever(results, relevance=0.7), backend, score_threshold=0.4, reasoning=True
    )
    rag.ask("מה השאלה")
    # The second (synthesis) call sees the study map, the numbered sources, the question.
    _system, messages = backend.calls[1]
    synth_user = messages[0].content
    assert "STUDY MAP" in synth_user
    assert "MAP: [S1] says X." in synth_user  # the stage-1 output is threaded in
    assert "[S1] (Tanya 1:1) טקסט" in synth_user
    assert "מה השאלה" in synth_user


def test_single_pass_unchanged_when_reasoning_off() -> None:
    # Default (reasoning off) => exactly one model call, no study map.
    backend = RecordingBackend(reply="plain answer [S1].")
    results = [_result("Tanya 1:1", "א")]
    rag = RAGService(FakeRetriever(results, relevance=0.7), backend, score_threshold=0.4)
    answer = rag.ask("שאלה")
    assert len(backend.calls) == 1
    assert answer.reasoning is None
    assert answer.unsupported_claims == []


def test_reasoning_default_deny_makes_no_calls() -> None:
    backend = SequencedBackend(["should not be used", "nor this"])
    rag = RAGService(
        FakeRetriever([], relevance=0.0), backend, score_threshold=0.4, reasoning=True, verify=True
    )
    answer = rag.ask("שאלה")
    assert answer.grounded is False
    assert backend.systems == []  # default-deny fires before any stage


def test_verify_flags_unsupported_sentences() -> None:
    # reasoning off + verify on => 2 calls (answer, then verify).
    backend = SequencedBackend(["claim one [S1]. claim two [S1].", "claim two [S1]."])
    results = [_result("Tanya 1:1", "א")]
    rag = RAGService(
        FakeRetriever(results, relevance=0.7), backend, score_threshold=0.4, verify=True
    )
    answer = rag.ask("שאלה")
    assert len(backend.systems) == 2
    assert answer.unsupported_claims == ["claim two [S1]."]


def test_verify_ok_yields_no_flags() -> None:
    backend = SequencedBackend(["supported [S1].", "OK"])
    results = [_result("Tanya 1:1", "א")]
    rag = RAGService(
        FakeRetriever(results, relevance=0.7), backend, score_threshold=0.4, verify=True
    )
    answer = rag.ask("שאלה")
    assert answer.unsupported_claims == []
