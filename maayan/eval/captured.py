"""The eval flywheel (Prompt 38): every gated approval auto-drafts a regression case.

The software rule "every bug fix ships with a test," applied to knowledge: when a
connection / development / term passes its gate (or an inquiry is answered), a
`CapturedExample` is drafted DETERMINISTICALLY — templates only, no model calls —
and stored. `maayan eval --captured` runs the existing retrieval harness over the
set, so every approval becomes a permanent retrievability check and improvements
are provable, not vibes.

Hygiene mirrors the rest of the system: identical questions update rather than
duplicate (ids derive from the folded question), and retracting the origin
retracts the example (the retract service calls `retract_origin`). The recorder
is a small injected hook on the EXISTING approval paths — services call one
method; all drafting logic lives here.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from maayan.capture.models import Annotation
from maayan.capture.store import CaptureStore
from maayan.clock import Clock, SystemClock
from maayan.config import Settings
from maayan.corpus.normalize import fold_surface
from maayan.develop.models import Development
from maayan.eval.goldset import GoldExample
from maayan.inquiry.models import InquiryItem, RefusedQuestionPayload
from maayan.lexicon.models import Term

OriginKind = Literal["connection", "development", "term", "inquiry"]

# Identical questions update rather than duplicate: the id IS the folded question.
_CAPTURED_NS = uuid.UUID("9f6a4d2c-04c1-4b3e-9c07-6c1cf17d2b58")


def captured_id(question: str) -> str:
    return str(uuid.uuid5(_CAPTURED_NS, fold_surface(question)))


class CapturedOrigin(BaseModel):
    """What approval drafted this example — the retract flow keys on `source_id`."""

    kind: OriginKind
    source_id: str


class CapturedExample(BaseModel):
    """One machine-grown regression case (stratum 'captured', vs the expert's exam)."""

    id: str
    question: str
    expected_refs: list[str] = Field(default_factory=list)
    gold_answer: str
    stratum: Literal["captured"] = "captured"
    origin: CapturedOrigin
    created_at: datetime
    retracted: bool = False


class CapturedGoldsetStore:
    """SQLite persistence for captured examples (same DB file as the rest)."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS captured_examples (
        id            TEXT PRIMARY KEY,
        question      TEXT NOT NULL,
        expected_refs TEXT NOT NULL,   -- json array
        gold_answer   TEXT NOT NULL,
        origin_kind   TEXT NOT NULL,
        origin_id     TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        retracted     INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_captured_origin ON captured_examples(origin_id);
    """

    def __init__(self, db_path: str) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()

    def upsert(self, example: CapturedExample) -> CapturedExample:
        """Insert or update-in-place (identical question → same id → update)."""
        self._conn.execute(
            "INSERT INTO captured_examples (id, question, expected_refs, gold_answer, "
            "origin_kind, origin_id, created_at, retracted) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET expected_refs = excluded.expected_refs, "
            "gold_answer = excluded.gold_answer, origin_kind = excluded.origin_kind, "
            "origin_id = excluded.origin_id, retracted = 0",
            (
                example.id,
                example.question,
                json.dumps(example.expected_refs, ensure_ascii=False),
                example.gold_answer,
                example.origin.kind,
                example.origin.source_id,
                example.created_at.isoformat(),
                int(example.retracted),
            ),
        )
        self._conn.commit()
        return example

    def get(self, example_id: str) -> CapturedExample | None:
        row = self._conn.execute(
            "SELECT * FROM captured_examples WHERE id = ?", (example_id,)
        ).fetchone()
        return self._row_to_example(row) if row else None

    def list_examples(self, *, include_retracted: bool = False) -> list[CapturedExample]:
        where = "" if include_retracted else "WHERE retracted = 0"
        rows = self._conn.execute(
            f"SELECT * FROM captured_examples {where} ORDER BY created_at, id"
        )
        return [self._row_to_example(r) for r in rows]

    def retract_by_origin(self, origin_id: str) -> int:
        """Tombstone every example drafted from `origin_id`; returns how many."""
        cursor = self._conn.execute(
            "UPDATE captured_examples SET retracted = 1 WHERE origin_id = ? AND retracted = 0",
            (origin_id,),
        )
        self._conn.commit()
        return cursor.rowcount

    def count(self, *, include_retracted: bool = False) -> int:
        where = "" if include_retracted else "WHERE retracted = 0"
        row = self._conn.execute(
            f"SELECT COUNT(*) AS n FROM captured_examples {where}"
        ).fetchone()
        return int(row["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> CapturedGoldsetStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_example(row: sqlite3.Row) -> CapturedExample:
        return CapturedExample(
            id=row["id"],
            question=row["question"],
            expected_refs=json.loads(row["expected_refs"]),
            gold_answer=row["gold_answer"],
            origin=CapturedOrigin(kind=row["origin_kind"], source_id=row["origin_id"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            retracted=bool(row["retracted"]),
        )


class CapturedRecorder:
    """The injected hook: one call per approval path, all drafting logic here.

    Templates only — a recorder that called a model would make the regression
    suite as unreliable as the thing it checks. Disabled (config) → every method
    is a no-op, so call sites never branch.
    """

    def __init__(
        self,
        store: CapturedGoldsetStore,
        clock: Clock,
        *,
        capture_store: CaptureStore | None = None,  # to read a development's seed
        enabled: bool = True,
    ) -> None:
        self._store = store
        self._clock = clock
        self._capture = capture_store
        self._enabled = enabled

    def record_connection(self, annotation: Annotation) -> CapturedExample | None:
        """Approved connection → 'מה הקשר בין X ל־Y?' expecting its linked refs."""
        if not self._enabled or annotation.kind != "connection":
            return None
        refs = [r for r in annotation.linked_refs if r.strip()]
        if len(refs) < 2 or not annotation.body.strip():
            return None
        question = f"מה הקשר בין {refs[0]} ל־{refs[1]}?"
        return self._save("connection", annotation.id, question, refs, annotation.body)

    def record_development(self, development: Development) -> CapturedExample | None:
        """Approved development → the seed's directive (it already reads as a question)."""
        if not self._enabled or development.status != "approved":
            return None
        directive = self._seed_directive(development.seed_id)
        if not directive or not development.grounded_in:
            return None
        return self._save(
            "development",
            development.id,
            directive,
            development.grounded_in,
            development.text,
        )

    def record_term(self, term: Term) -> CapturedExample | None:
        """Approved term → 'מהו {canonical}?' expecting the definition's grounding."""
        if not self._enabled or term.retracted or not term.source_refs:
            return None
        return self._save(
            "term", term.id, f"מהו {term.canonical}?", term.source_refs, term.definition
        )

    def record_inquiry(self, item: InquiryItem) -> CapturedExample | None:
        """Answered refused-question inquiry → the question + what resolving created.

        No expected refs are known at answer time, so the example is 'gate-only':
        `eval --captured` reports it separately (should now be answerable) and
        keeps it out of the ranking metrics.
        """
        if not self._enabled or item.status != "answered":
            return None
        payload = item.payload
        if not isinstance(payload, RefusedQuestionPayload) or not payload.questions:
            return None
        question = payload.questions[-1]
        return self._save("inquiry", item.id, question, [], item.resolution or "")

    def retract_origin(self, origin_id: str) -> int:
        """Origin retracted → its examples leave the suite (hygiene, audited upstream)."""
        if not self._enabled:
            return 0
        return self._store.retract_by_origin(origin_id)

    # -- internals -----------------------------------------------------------
    def _save(
        self, kind: OriginKind, source_id: str, question: str, refs: list[str], gold: str
    ) -> CapturedExample:
        return self._store.upsert(
            CapturedExample(
                id=captured_id(question),
                question=question,
                expected_refs=refs,
                gold_answer=gold,
                origin=CapturedOrigin(kind=kind, source_id=source_id),
                created_at=self._clock.now(),
            )
        )

    def _seed_directive(self, seed_id: str) -> str | None:
        if self._capture is None:
            return None
        seed = self._capture.get_annotation(seed_id)
        return seed.directive if seed is not None else None


def build_captured_recorder(settings: Settings, *, clock: Clock | None = None) -> CapturedRecorder:
    """Construction convenience for the factories (DI at the edge)."""
    return CapturedRecorder(
        CapturedGoldsetStore(settings.db_path),
        clock or SystemClock(),
        capture_store=CaptureStore(settings.db_path),
        enabled=settings.captured_goldset_enabled,
    )


def to_gold_examples(examples: list[CapturedExample]) -> list[GoldExample]:
    """Ref-bearing captured examples as inputs for the EXISTING retrieval harness."""
    return [
        GoldExample(
            question=ex.question,
            expected_refs=ex.expected_refs,
            answer=ex.gold_answer,
            stratum="captured",
        )
        for ex in examples
        if ex.expected_refs
    ]


class CapturedRunRecord(BaseModel):
    """One dated `eval --captured` result — the JSON artifact runs are trended by."""

    date: str
    n_ranked: int
    n_gate_only: int
    gate_only_answered: int
    ks: list[int]
    hit: dict[str, float]  # str keys: JSON round-trips them unchanged
    recall: dict[str, float]
    mrr: float
    answer_rate: float


def write_captured_report(record: CapturedRunRecord, reports_dir: str) -> Path:
    """Persist a run as `captured_<date>.json` (filename order == run order)."""
    directory = Path(reports_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = record.date.replace(":", "").replace("-", "").replace("+0000", "Z")
    path = directory / f"captured_{stamp}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_previous_report(reports_dir: str) -> CapturedRunRecord | None:
    """The most recent prior run in the reports dir, if any."""
    directory = Path(reports_dir)
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob("captured_*.json"))
    if not candidates:
        return None
    return CapturedRunRecord.model_validate_json(candidates[-1].read_text(encoding="utf-8"))


def format_delta(current: CapturedRunRecord, previous: CapturedRunRecord | None) -> str:
    """Trend line vs the previous run — the flywheel made visible."""
    if previous is None:
        return "(first captured run — no previous report to diff against)"
    lines = [f"vs previous run ({previous.date}):"]
    lines.append(f"  examples: {previous.n_ranked} → {current.n_ranked} ranked")
    for k in current.ks:
        key = str(k)
        if key in previous.hit:
            lines.append(f"  hit@{k}: {previous.hit[key]:.3f} → {current.hit[key]:.3f} "
                         f"({current.hit[key] - previous.hit[key]:+.3f})")
    lines.append(f"  MRR: {previous.mrr:.3f} → {current.mrr:.3f} "
                 f"({current.mrr - previous.mrr:+.3f})")
    lines.append(f"  answered rate: {previous.answer_rate:.3f} → {current.answer_rate:.3f} "
                 f"({current.answer_rate - previous.answer_rate:+.3f})")
    return "\n".join(lines)
