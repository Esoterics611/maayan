"""Chazarah scheduler (Prompt 41): resurface aging, low-evidence, unused knowledge.

A pass (no daemon — Clock-driven, run on demand) that queues ``re_review`` inquiry
items for approved relations that are:

* **stale bootstrap** — evidence ``derived_bootstrap`` and older than the configured
  window (the free drafter's edges, never yet human-checked);
* **low confidence** — below the inquiry confidence threshold;
* **never retrieved** — neither endpoint ref appears in any logged ask's citations
  (join AskLog ↔ citations), so no answer has ever leaned on it.

Each target gets an Anki-style schedule: it is due immediately when first detected, and
every confirmation (`ScheduleStore.confirm`) multiplies its next-review interval. The
scheduler only *proposes* review — nothing is judged or retracted here.
"""

from __future__ import annotations

from maayan.clock import Clock
from maayan.config import Settings
from maayan.consolidate.models import ChazarahReport
from maayan.consolidate.schedule_store import ScheduleStore
from maayan.graph.models import Relation, endpoint_key, endpoint_str
from maayan.graph.store import GraphStore
from maayan.inquiry.generate import rank
from maayan.inquiry.log import AskLog
from maayan.inquiry.models import InquiryItem, ReReviewPayload, inquiry_id
from maayan.inquiry.store import InquiryStore


class ChazarahScheduler:
    """Queue re-review inquiries for knowledge that has aged past its evidence."""

    def __init__(
        self,
        graph: GraphStore,
        ask_log: AskLog,
        inquiries: InquiryStore,
        schedule: ScheduleStore,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self._graph = graph
        self._ask_log = ask_log
        self._inquiries = inquiries
        self._schedule = schedule
        self._clock = clock
        self._settings = settings

    def run(self) -> ChazarahReport:
        """One chazarah pass: schedule candidates, queue the due ones. Idempotent."""
        report = ChazarahReport()
        cited = self._ask_log.cited_refs_ever()
        have_asks = bool(cited) or self._ask_log.count() > 0
        for relation, reason in self._candidates(cited, have_asks=have_asks):
            self._schedule.ensure(
                relation.id,
                "relation",
                base_interval_days=self._settings.chazarah_base_interval_days,
            )
            report.scheduled += 1
            schedule = self._schedule.get(relation.id)
            assert schedule is not None  # just ensured
            if schedule.next_review_at <= self._clock.now():
                self._queue(relation, reason)
                report.queued += 1
                report.by_reason[reason] = report.by_reason.get(reason, 0) + 1
        return report

    def confirm(self, target_id: str) -> None:
        """Confirm a re-review — multiply the interval (spaced repetition)."""
        self._schedule.confirm(target_id, factor=self._settings.chazarah_interval_factor)

    # -- internals ---------------------------------------------------------------
    def _candidates(
        self, cited: set[str], *, have_asks: bool
    ) -> list[tuple[Relation, str]]:
        """Approved relations due for chazarah, each with the reason (first match)."""
        now = self._clock.now()
        out: list[tuple[Relation, str]] = []
        for relation in self._graph.list_relations(status="approved"):
            age_days = (now - relation.created_at).total_seconds() / 86400.0
            reason: str | None = None
            if (
                relation.evidence == "derived_bootstrap"
                and age_days >= self._settings.chazarah_bootstrap_days
            ):
                reason = "stale_bootstrap"
            elif relation.confidence < self._settings.inquiry_confidence_threshold:
                reason = "low_confidence"
            elif have_asks and self._never_retrieved(relation, cited):
                reason = "never_retrieved"
            if reason is not None:
                out.append((relation, reason))
        return out

    @staticmethod
    def _never_retrieved(relation: Relation, cited: set[str]) -> bool:
        """True when neither ref endpoint has ever been cited in a logged ask."""
        refs = [
            value
            for value in (
                endpoint_key(relation.subject),
                endpoint_key(relation.object),
            )
            if value[0] == "ref"
        ]
        if not refs:  # a concept↔concept edge has no ref to have been retrieved by
            return False
        return all(value not in cited for _kind, value in refs)

    def _queue(self, relation: Relation, reason: str) -> None:
        """Upsert one re_review inquiry for a relation (deterministic id → dedupe)."""
        subject, obj = endpoint_str(relation.subject), endpoint_str(relation.object)
        detail_by_reason = {
            "stale_bootstrap": "מקורו ב-bootstrap ולא נבדק מזמן — לאשר, לתקן או לדחות.",
            "low_confidence": "רמת ביטחון נמוכה — חזרה לאישור.",
            "never_retrieved": "אף תשובה מעולם לא נשענה עליו — עדיין רלוונטי?",
        }
        priority, parts = rank(
            "re_review",
            count=1,
            last_seen=relation.created_at,
            clock=self._clock,
            settings=self._settings,
        )
        item = InquiryItem(
            id=inquiry_id("re_review", relation.id),
            kind="re_review",
            title=f"חזרה: הקשר {subject} —{relation.rel_type}→ {obj} ({reason}).",
            detail=detail_by_reason.get(reason, "חזרה על ידע ותיק."),
            payload=ReReviewPayload(
                target_id=relation.id, target_kind="relation", reason=reason
            ),
            priority=priority,
            priority_parts=parts,
            created_at=self._clock.now(),
        )
        self._inquiries.upsert_open(item)
