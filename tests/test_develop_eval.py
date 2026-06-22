"""Tests for the develop eval — metrics (hand-checked), aggregation, gold-set guard.

No network and no real models: the develop step runs through the REAL
DevelopmentService wired to a fake retriever (relevance keyed by a marker in the
seed) and a recording backend, so the default-deny gate and citation extraction are
exercised for real while staying offline.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from maayan.clock import FakeClock
from maayan.config import Settings
from maayan.corpus.store import ChunkStore
from maayan.develop.service import DevelopmentService
from maayan.develop.store import DevelopmentStore
from maayan.embed.fake import HashingEmbedder
from maayan.eval.develop_goldset import DevelopGoldExample, load_develop_goldset
from maayan.eval.develop_harness import (
    DevelopReport,
    format_develop_report,
    run_develop_eval,
)
from maayan.eval.develop_metrics import grounding_score
from maayan.generate.base import Message
from maayan.index.qdrant import QdrantIndex
from maayan.retrieve.models import RetrievalResult, SearchResult
from maayan.threads.service import ThreadService
from maayan.threads.store import ThreadStore

DIM = 64
SUPPORTED = "YES-CORPUS"  # marker the fake retriever treats as well-supported
UNSUPPORTED = "NO-CORPUS"


# -- metric: grounding (cited ⊆ retrieved), hand-checked -----------------------
def test_grounding_score_catches_fabricated_citations() -> None:
    retrieved = ["Tanya 1:6", "Tanya 9:1"]
    assert grounding_score(["Tanya 1:6", "Tanya 9:1"], retrieved) == pytest.approx(1.0)
    # One cited ref was never retrieved → fabrication → 0.5.
    assert grounding_score(["Tanya 1:6", "Tanya 99:9"], retrieved) == pytest.approx(0.5)
    assert grounding_score(["Tanya 99:9"], retrieved) == pytest.approx(0.0)
    assert grounding_score([], retrieved) == pytest.approx(1.0)  # nothing to fabricate


# -- harness aggregation with a real service + fakes --------------------------
class _KeyedRetriever:
    """Returns fixed results; relevance is high iff the query carries the supported marker."""

    def __init__(self, results: list[SearchResult], *, high: float, low: float) -> None:
        self._results = results
        self._high = high
        self._low = low

    def retrieve(self, query: str, *, k=None, book=None, source=None) -> RetrievalResult:
        relevance = self._high if SUPPORTED in query else self._low
        return RetrievalResult(results=self._results, relevance=relevance)


class _RecordingBackend:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        self.calls += 1
        return self.reply


def _result(ref: str) -> SearchResult:
    return SearchResult(ref=ref, text="t", score=0.6, lang="he", source="sefaria", payload={})


def _setup(backend: _RecordingBackend) -> tuple[DevelopmentService, ThreadService]:
    threads = ThreadService(ThreadStore(":memory:"), FakeClock())
    retriever = _KeyedRetriever([_result("Tanya 1:6"), _result("Tanya 9:1")], high=0.7, low=0.1)
    settings = Settings(score_threshold=0.4, develop_top_k=5)
    service = DevelopmentService(
        retriever, backend, DevelopmentStore(":memory:"), threads, FakeClock(),
        settings, HashingEmbedder(dim=DIM),
        ChunkStore(":memory:"), QdrantIndex(QdrantClient(location=":memory:"), "t", DIM),
    )
    return service, threads


def _gold() -> list[DevelopGoldExample]:
    return [
        DevelopGoldExample(body=f"{SUPPORTED} seed one", directive="develop", supported=True),
        DevelopGoldExample(body=f"{SUPPORTED} seed two", directive="develop", supported=True),
        DevelopGoldExample(body=f"{UNSUPPORTED} seed three", directive="develop", supported=False),
        DevelopGoldExample(body=f"{UNSUPPORTED} seed four", directive="develop", supported=False),
    ]


def test_run_develop_eval_perfect_run() -> None:
    backend = _RecordingBackend(reply="developed, grounded in [S1].")
    service, threads = _setup(backend)

    report = run_develop_eval(service, threads, FakeClock(), _gold())

    assert report.n == 4
    assert report.n_supported == 2 and report.n_unsupported == 2
    assert report.n_developed == 2  # only the two supported seeds were developed
    assert report.develop_rate == pytest.approx(1.0)  # both supported developed
    assert report.refusal_rate == pytest.approx(1.0)  # both unsupported refused
    assert report.grounding == pytest.approx(1.0)  # cited [S1] → Tanya 1:6, which was retrieved
    assert backend.calls == 2  # default-deny: no model call for the two unsupported seeds


def test_run_develop_eval_counts_over_refusal_and_forced_development() -> None:
    # Threshold so high that NOTHING clears it → every seed refuses, including supported.
    backend = _RecordingBackend(reply="[S1]")
    threads = ThreadService(ThreadStore(":memory:"), FakeClock())
    retriever = _KeyedRetriever([_result("Tanya 1:6")], high=0.7, low=0.1)
    settings = Settings(score_threshold=0.99, develop_top_k=5)
    service = DevelopmentService(
        retriever, backend, DevelopmentStore(":memory:"), threads, FakeClock(),
        settings, HashingEmbedder(dim=DIM),
        ChunkStore(":memory:"), QdrantIndex(QdrantClient(location=":memory:"), "t", DIM),
    )

    report = run_develop_eval(service, threads, FakeClock(), _gold())

    assert report.develop_rate == pytest.approx(0.0)  # supported seeds wrongly refused
    assert report.refusal_rate == pytest.approx(1.0)  # unsupported correctly refused
    assert report.n_developed == 0
    assert backend.calls == 0  # nothing cleared the gate


def test_format_develop_report_renders_numbers() -> None:
    report = DevelopReport(
        n=4, n_supported=2, n_unsupported=2, n_developed=2,
        develop_rate=1.0, refusal_rate=0.5, grounding=0.75,
    )
    text = format_develop_report(report)
    assert "4 seeds (2 supported, 2 unsupported)" in text
    assert "developed (of supported):" in text
    assert "0.750" in text  # grounding


def test_format_develop_report_handles_no_developed() -> None:
    report = DevelopReport(
        n=2, n_supported=0, n_unsupported=2, n_developed=0,
        develop_rate=0.0, refusal_rate=1.0, grounding=0.0,
    )
    text = format_develop_report(report)
    assert "n/a" in text  # grounding + develop-rate have no examples → n/a, not 0.000


def test_shipped_develop_goldset_is_well_formed() -> None:
    """Guard the real eval/develop_goldset.yaml in CI (no model needed)."""
    path = Path(__file__).resolve().parents[1] / "eval" / "develop_goldset.yaml"
    examples = load_develop_goldset(str(path))
    supported = [e for e in examples if e.supported]
    unsupported = [e for e in examples if not e.supported]
    assert len(examples) >= 8, "want ~8 seeds"
    assert supported and unsupported, "need both supported and unsupported seeds"
    for e in examples:
        assert e.body.strip(), "every seed needs a body"
        assert e.author.strip(), "every seed needs a (non-blank) author"
