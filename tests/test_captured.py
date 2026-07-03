"""Tests for Prompt 38 — the eval flywheel.

Every approval kind drafts its deterministic example (templates, no model),
identical questions update rather than duplicate, retraction removes examples,
and `eval --captured` math (run over in-memory Qdrant) + trend deltas work.
"""

from __future__ import annotations

from datetime import UTC, datetime

from qdrant_client import QdrantClient

from maayan.capture.models import Annotation
from maayan.capture.service import CaptureService
from maayan.capture.store import CaptureStore
from maayan.clock import FakeClock
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.develop.models import Development
from maayan.embed.fake import HashingEmbedder
from maayan.eval.captured import (
    CapturedGoldsetStore,
    CapturedRecorder,
    CapturedRunRecord,
    captured_id,
    format_delta,
    load_previous_report,
    to_gold_examples,
    write_captured_report,
)
from maayan.eval.harness import run_eval
from maayan.graph.store import GraphStore
from maayan.index.pipeline import index_chunks
from maayan.index.qdrant import QdrantIndex
from maayan.inquiry.log import AskLog
from maayan.inquiry.store import InquiryStore
from maayan.lexicon.models import Term
from maayan.retrieve.retriever import Retriever

T0 = datetime(2026, 7, 1, tzinfo=UTC)
TANYA = "Tanya, Part I; Likkutei Amarim 18:1"
TORAH_OHR = "Torah Ohr, Vayera 14:1"
DIM = 128


def _recorder(
    *, enabled: bool = True, capture_store: CaptureStore | None = None
) -> tuple[CapturedRecorder, CapturedGoldsetStore]:
    store = CapturedGoldsetStore(":memory:")
    return (
        CapturedRecorder(store, FakeClock(T0), capture_store=capture_store, enabled=enabled),
        store,
    )


def _connection(refs: list[str], *, body: str = "שני המקורות מדברים על אהבה מסותרת") -> Annotation:
    return Annotation(
        id="ann-1", session_id="s-1", timestamp=T0, author="R. Ginsburgh",
        kind="connection", body=body, linked_refs=refs,
    )


# -- drafting per approval kind ---------------------------------------------------

def test_connection_drafts_a_kesher_question() -> None:
    recorder, store = _recorder()
    example = recorder.record_connection(_connection([TANYA, TORAH_OHR]))

    assert example is not None
    assert example.question == f"מה הקשר בין {TANYA} ל־{TORAH_OHR}?"
    assert example.expected_refs == [TANYA, TORAH_OHR]
    assert example.gold_answer == "שני המקורות מדברים על אהבה מסותרת"
    assert example.origin.kind == "connection" and example.origin.source_id == "ann-1"
    assert store.count() == 1


def test_non_connections_short_ref_lists_and_disabled_flag_draft_nothing() -> None:
    recorder, store = _recorder()
    correction = _connection([TANYA, TORAH_OHR]).model_copy(update={"kind": "correction"})
    assert recorder.record_connection(correction) is None
    assert recorder.record_connection(_connection([TANYA])) is None

    disabled, disabled_store = _recorder(enabled=False)
    assert disabled.record_connection(_connection([TANYA, TORAH_OHR])) is None
    assert store.count() == 0 and disabled_store.count() == 0


def test_development_drafts_from_the_seed_directive() -> None:
    capture = CaptureStore(":memory:")
    seed = _connection([TANYA]).model_copy(update={
        "id": "seed-1", "kind": "addition", "opens_aspect": True,
        "directive": "מצא היכן זה נרמז בתניא",
    })
    capture.save_annotation(seed)
    recorder, _ = _recorder(capture_store=capture)
    dev = Development(
        id="dev-1", thread_id="t-1", seed_id="seed-1", author="R. Ginsburgh",
        timestamp=T0, model="m", status="approved", grounded=True,
        text="הפיתוח המבוסס", cited_refs=[TANYA], grounded_in=[TANYA],
    )

    example = recorder.record_development(dev)

    assert example is not None
    assert example.question == "מצא היכן זה נרמז בתניא"
    assert example.expected_refs == [TANYA]
    assert example.origin.kind == "development"

    # No directive (or no capture store) → nothing drafted, never a guess.
    bare = dev.model_copy(update={"seed_id": "missing"})
    assert recorder.record_development(bare) is None


def test_term_drafts_mahu_question_from_its_grounding() -> None:
    recorder, _ = _recorder()
    term = Term(
        id="term-1", canonical="ביטול", definition="התכללות באור אין סוף",
        source_refs=[TANYA], author="R. Ginsburgh",
    )
    example = recorder.record_term(term)
    assert example is not None
    assert example.question == "מהו ביטול?"
    assert example.expected_refs == [TANYA]
    # A term with no grounding refs cannot become a retrieval check.
    bare = term.model_copy(update={"id": "term-2", "source_refs": []})
    assert recorder.record_term(bare) is None


def test_answered_inquiry_drafts_a_gate_only_example() -> None:
    clock = FakeClock(T0)
    goldset = CapturedGoldsetStore(":memory:")
    recorder = CapturedRecorder(goldset, clock)
    log = AskLog(":memory:", clock)
    inquiries = InquiryStore(":memory:", clock, recorder=recorder)
    log.record(question="מהו ביטול במקום?", refused=True, top_score=0.1)
    from maayan.config import Settings
    from maayan.inquiry.generate import generate_inquiries

    generate_inquiries(inquiries, clock, Settings(_env_file=None), ask_log=log)
    item = inquiries.list(status="open")[0]

    inquiries.mark_answered(item.id, resolution="expert chunk exp_9f2")

    examples = goldset.list_examples()
    assert len(examples) == 1
    assert examples[0].question == "מהו ביטול במקום?"
    assert examples[0].expected_refs == []  # gate-only: should now be answerable
    assert examples[0].gold_answer == "expert chunk exp_9f2"
    assert to_gold_examples(examples) == []  # kept out of the ranking metrics


# -- dedupe + retraction hygiene ---------------------------------------------------

def test_identical_questions_update_rather_than_duplicate() -> None:
    recorder, store = _recorder()
    recorder.record_connection(_connection([TANYA, TORAH_OHR], body="גרסה ראשונה"))
    recorder.record_connection(
        _connection([TANYA, TORAH_OHR], body="גרסה מתוקנת").model_copy(update={"id": "ann-2"})
    )
    examples = store.list_examples()
    assert len(examples) == 1
    assert examples[0].gold_answer == "גרסה מתוקנת"
    assert examples[0].origin.source_id == "ann-2"
    assert captured_id(examples[0].question) == examples[0].id


def test_retracting_the_origin_retracts_the_example() -> None:
    recorder, store = _recorder()
    recorder.record_connection(_connection([TANYA, TORAH_OHR]))
    assert store.count() == 1

    assert recorder.retract_origin("ann-1") == 1
    assert store.count() == 0
    assert store.count(include_retracted=True) == 1  # tombstoned, not deleted
    assert store.list_examples() == []

    # Re-approval resurrects it (upsert clears the tombstone).
    recorder.record_connection(_connection([TANYA, TORAH_OHR]))
    assert store.count() == 1


def test_capture_service_records_connections_end_to_end() -> None:
    goldset = CapturedGoldsetStore(":memory:")
    clock = FakeClock(T0)
    recorder = CapturedRecorder(goldset, clock)
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    service = CaptureService(
        CaptureStore(":memory:"), ChunkStore(":memory:"), embedder, index, clock,
        allowed_kinds=("connection", "correction"), recorder=recorder,
    )

    service.add_annotation(
        "s-1", author="R. Ginsburgh", kind="connection",
        body="קשר עמוק", linked_refs=[TANYA, TORAH_OHR],
    )
    service.add_annotation("s-1", author="R. Ginsburgh", kind="correction", body="תיקון")

    assert goldset.count() == 1  # the connection, not the correction


def test_retraction_service_cascade_removes_the_example() -> None:
    goldset = CapturedGoldsetStore(":memory:")
    clock = FakeClock(T0)
    recorder = CapturedRecorder(goldset, clock)
    chunks = ChunkStore(":memory:")
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    index.ensure_collection()
    from maayan.develop.store import DevelopmentStore
    from maayan.lexicon.store import TermStore
    from maayan.retract.service import RetractionService
    from maayan.retract.store import RetractionStore

    svc = RetractionService(
        chunks, RetractionStore(":memory:"), index, clock,
        DevelopmentStore(":memory:"), TermStore(":memory:"), GraphStore(":memory:"),
        recorder=recorder,
    )
    annotation = _connection([TANYA, TORAH_OHR])
    recorder.record_connection(annotation)
    chunk = Chunk.make(
        ref="Expert · connection · ann-1", book="Expert", section_path=["connection"],
        lang="he", text="קשר", source="expert",
        metadata={"author": "R. Ginsburgh", "contribution_id": "ann-1"},
    )
    chunks.upsert_chunks([chunk])

    svc.retract(chunk.ref, author="Editor", reason="wrong")

    assert goldset.count() == 0  # the regression case left with its origin


# -- eval --captured over in-memory qdrant + trend deltas ----------------------------

def test_captured_examples_run_through_the_existing_harness() -> None:
    recorder, store = _recorder()
    recorder.record_connection(_connection([TANYA, TORAH_OHR]))
    chunks = ChunkStore(":memory:")
    embedder = HashingEmbedder(dim=DIM)
    index = QdrantIndex(QdrantClient(location=":memory:"), "t", DIM)
    chunks.upsert_chunks([
        Chunk.make(ref=TANYA, book="Tanya", section_path=["18"], lang="he",
                   text=f"מה הקשר בין {TANYA} ל־{TORAH_OHR}? אהבה מסותרת", source="sefaria"),
        Chunk.make(ref=TORAH_OHR, book="Torah Ohr", section_path=["14"], lang="he",
                   text="עניין אחר לגמרי", source="sefaria"),
    ])
    index_chunks(store=chunks, embedder=embedder, index=index, batch_size=8)
    retriever = Retriever(index, embedder, top_k=5)

    gold = to_gold_examples(store.list_examples())
    report = run_eval(retriever, gold, [1, 5], score_threshold=0.5)

    assert report.n == 1
    assert report.hit[1] == 1.0  # the drafted question retrieves its own connection
    assert report.recall[5] == 1.0


def test_report_round_trip_and_delta(tmp_path) -> None:  # noqa: ANN001
    reports = str(tmp_path / "captured_reports")
    first = CapturedRunRecord(
        date="2026-07-01T00:00:00+00:00", n_ranked=1, n_gate_only=0, gate_only_answered=0,
        ks=[1], hit={"1": 0.5}, recall={"1": 0.5}, mrr=0.5, answer_rate=0.5,
    )
    write_captured_report(first, reports)
    second = CapturedRunRecord(
        date="2026-07-02T00:00:00+00:00", n_ranked=2, n_gate_only=1, gate_only_answered=1,
        ks=[1], hit={"1": 1.0}, recall={"1": 1.0}, mrr=1.0, answer_rate=1.0,
    )
    previous = load_previous_report(reports)
    assert previous is not None and previous.date == first.date

    delta = format_delta(second, previous)
    assert "hit@1: 0.500 → 1.000 (+0.500)" in delta
    assert "1 → 2 ranked" in delta
    assert "(first captured run" in format_delta(first, None)
