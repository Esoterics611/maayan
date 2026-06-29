"""Tests for the independent faithfulness judge (backend mocked)."""

from __future__ import annotations

from collections.abc import Sequence

from maayan.eval.judge import LLMJudge, build_judge_messages
from maayan.generate.base import Message
from maayan.retrieve.models import SearchResult


class ScriptedBackend:
    """Returns one canned reply; records the call."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, list[Message]]] = []

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        return self.reply


def _src(ref: str, text: str) -> SearchResult:
    return SearchResult(ref=ref, text=text, score=0.5, lang="he", source="sefaria", payload={})


SOURCES = [_src("Tanya 1:1", "טקסט ראשון"), _src("Tanya 1:2", "טקסט שני")]


def test_ok_reply_is_faithful() -> None:
    judge = LLMJudge(ScriptedBackend("OK"))
    verdict = judge.judge("q", "answer grounded in [S1].", SOURCES)
    assert verdict.faithful is True
    assert verdict.unsupported_claims == []


def test_listed_sentences_are_unfaithful() -> None:
    judge = LLMJudge(ScriptedBackend("Claim A is not supported.\nClaim B overstates [S2]."))
    verdict = judge.judge("q", "Claim A is not supported. Claim B overstates [S2].", SOURCES)
    assert verdict.faithful is False
    assert verdict.unsupported_claims == ["Claim A is not supported.", "Claim B overstates [S2]."]


def test_message_carries_sources_question_and_answer() -> None:
    backend = ScriptedBackend("OK")
    LLMJudge(backend).judge("מה השאלה", "the answer [S1].", SOURCES)
    content = backend.calls[0][1][0].content
    assert "[S1] (Tanya 1:1) טקסט ראשון" in content   # same numbering the answer used
    assert "מה השאלה" in content
    assert "the answer [S1]." in content


def test_build_judge_messages_shape() -> None:
    msgs = build_judge_messages("q", "a [S1].", SOURCES)
    assert len(msgs) == 1 and msgs[0].role == "user"
