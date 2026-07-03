"""Inquiry generators: turn telemetry, deny-lists, and graph weaknesses into
questions for the Rav.

Each generator is independent (and independently tested); the orchestrator runs
whichever ones have their dependency injected and upserts the drafts through the
store's dedupe. Priority is a config-weighted blend and every item carries its
own arithmetic (`priority_parts`) — the plan's rule: keep it transparent, print
the components.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from maayan.clock import Clock
from maayan.config import Settings
from maayan.corpus.normalize import fold_surface
from maayan.graph.models import Relation, endpoint_str
from maayan.graph.store import GraphStore
from maayan.inquiry.log import AskLog
from maayan.inquiry.models import (
    ContradictionPayload,
    GenerateReport,
    InquiryItem,
    InquiryKind,
    InquiryPayload,
    LowEvidenceRelationPayload,
    RefusedQuestionPayload,
    UndergroundedTermPayload,
    inquiry_id,
)
from maayan.inquiry.store import InquiryStore
from maayan.lexicon.populate import TermSuggestion

# The rel_types that CLAIM agreement/continuity — an approved argues_with edge on
# the same endpoints contradicts any of these. Surfaced, never auto-judged.
AGREEING_REL_TYPES = frozenset({"explains", "develops", "parallels"})


class SuggestionSource(Protocol):
    """The one lexicon-populate read the generator needs (DI seam)."""

    def list(self, *, status: str | None = None) -> list[TermSuggestion]:
        ...


def rank(
    kind: InquiryKind,
    *,
    count: int,
    last_seen: datetime,
    clock: Clock,
    settings: Settings,
) -> tuple[float, dict[str, float]]:
    """Priority = weighted count + weighted recency + kind base. Parts are printed."""
    age_days = max((clock.now() - last_seen).total_seconds() / 86400.0, 0.0)
    recency = 1.0 / (1.0 + age_days / settings.inquiry_recency_halflife_days)
    parts = {
        "count": round(settings.inquiry_count_weight * count, 2),
        "recency": round(settings.inquiry_recency_weight * recency, 2),
        "kind": settings.inquiry_kind_weights.get(kind, 1.0),
    }
    return sum(parts.values()), parts


def _item(
    kind: InquiryKind,
    dedupe_key: str,
    title: str,
    detail: str,
    payload: InquiryPayload,
    *,
    count: int,
    last_seen: datetime,
    clock: Clock,
    settings: Settings,
) -> InquiryItem:
    priority, parts = rank(kind, count=count, last_seen=last_seen, clock=clock, settings=settings)
    return InquiryItem(
        id=inquiry_id(kind, dedupe_key),
        kind=kind,
        title=title,
        detail=detail,
        payload=payload,
        priority=priority,
        priority_parts=parts,
        created_at=clock.now(),
    )


# -- generators --------------------------------------------------------------------

def refused_questions(
    ask_log: AskLog, clock: Clock, settings: Settings
) -> list[InquiryItem]:
    """Cluster refusals (near-duplicate by folded text — v1) into one item each."""
    clusters: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    last: dict[str, datetime] = {}
    for record in ask_log.list_refused():
        key = fold_surface(record.question)
        if not key:
            continue
        variants = clusters.setdefault(key, [])
        if record.question not in variants:
            variants.append(record.question)
        counts[key] = counts.get(key, 0) + 1
        last[key] = record.timestamp
    items: list[InquiryItem] = []
    for key, variants in clusters.items():
        count = counts[key]
        head = variants[-1]
        title = (
            f"{count} שאלות על נושא זה — המערכת סירבה בכל פעם: «{head}»"
            if count > 1
            else f"שאלה שנותרה ללא מענה: «{head}»"
        )
        items.append(
            _item(
                "refused_question",
                key,
                title,
                "הקורפוס לא תמך בתשובה. הוספת מקור/קשר/מונח תסגור את הפער.",
                RefusedQuestionPayload(questions=variants, count=count, last_asked=last[key]),
                count=count,
                last_seen=last[key],
                clock=clock,
                settings=settings,
            )
        )
    return items


def undergrounded_terms(
    suggestions: SuggestionSource, clock: Clock, settings: Settings
) -> list[InquiryItem]:
    """Deny-list entries: terms the free drafter failed to ground. Confirm or dismiss."""
    items: list[InquiryItem] = []
    for suggestion in suggestions.list(status="pending"):
        if suggestion.supported:
            continue  # grounded fine — it waits in the normal review queue, not here
        title = (
            f"ייתכן שהקורפוס תומך ב־«{suggestion.canonical}» — המנסח החינמי נכשל. "
            "לאשר או לדחות?"
        )
        detail = (
            f"טיוטה של {suggestion.model or 'המנסח'} לא עברה את בדיקת הנאמנות; "
            "נסח מחדש דרך add-term או דחה."
        )
        items.append(
            _item(
                "undergrounded_term",
                suggestion.canonical,
                title,
                detail,
                UndergroundedTermPayload(
                    canonical=suggestion.canonical,
                    suggestion_id=suggestion.id,
                    model=suggestion.model,
                    unsupported_claims=suggestion.unsupported_claims,
                ),
                count=1,
                last_seen=suggestion.created_at,
                clock=clock,
                settings=settings,
            )
        )
    return items


def low_evidence_relations(
    graph: GraphStore, clock: Clock, settings: Settings
) -> list[InquiryItem]:
    """Approved edges standing on bootstrap evidence or low confidence."""
    items: list[InquiryItem] = []
    for relation in graph.list_relations(status="approved"):
        weak_evidence = relation.evidence == "derived_bootstrap"
        low_confidence = relation.confidence < settings.inquiry_confidence_threshold
        if not (weak_evidence or low_confidence):
            continue
        subject, obj = endpoint_str(relation.subject), endpoint_str(relation.object)
        why = "מקורו ב־bootstrap וטרם נבדק" if weak_evidence else "ברמת ביטחון נמוכה"
        items.append(
            _item(
                "low_evidence_relation",
                relation.id,
                f"הקשר {subject} ↔ {obj} {why}.",
                f"{relation.rel_type} · evidence {relation.evidence} · "
                f"confidence {relation.confidence:.2f} · {relation.author}",
                LowEvidenceRelationPayload(
                    relation_id=relation.id,
                    subject=subject,
                    object=obj,
                    rel_type=relation.rel_type,
                    evidence=relation.evidence,
                    confidence=relation.confidence,
                    author=relation.author,
                ),
                count=1,
                last_seen=relation.created_at,
                clock=clock,
                settings=settings,
            )
        )
    return items


def contradictions(graph: GraphStore, clock: Clock, settings: Settings) -> list[InquiryItem]:
    """Approved argues_with vs explains/develops/parallels on the same endpoints.

    v1 is honest and simple: surface the conflict, never judge it.
    """
    by_pair: dict[frozenset[str], list[Relation]] = {}
    for relation in graph.list_relations(status="approved"):
        pair = frozenset({endpoint_str(relation.subject), endpoint_str(relation.object)})
        if len(pair) == 2:
            by_pair.setdefault(pair, []).append(relation)
    items: list[InquiryItem] = []
    for pair, relations in by_pair.items():
        argues = [r for r in relations if r.rel_type == "argues_with"]
        agrees = [r for r in relations if r.rel_type in AGREEING_REL_TYPES]
        if not argues or not agrees:
            continue
        a, b = argues[0], agrees[0]
        subject, obj = sorted(pair)
        items.append(
            _item(
                "contradiction",
                "|".join(sorted([a.id, b.id])),
                f"שני קשרים סותרים בין {subject} ל־{obj}: "
                f"`{a.rel_type}` מול `{b.rel_type}` — מי צודק?",
                f"{a.rel_type} ({a.author}) נגד {b.rel_type} ({b.author}). "
                "אשר אחד, דחה את השני — או השאר את שניהם עם הערה.",
                ContradictionPayload(
                    relation_a_id=a.id,
                    relation_b_id=b.id,
                    subject=subject,
                    object=obj,
                    rel_type_a=a.rel_type,
                    rel_type_b=b.rel_type,
                    authors=[a.author, b.author],
                ),
                count=1,
                last_seen=max(a.created_at, b.created_at),
                clock=clock,
                settings=settings,
            )
        )
    return items


# -- orchestrator --------------------------------------------------------------------

def generate_inquiries(
    store: InquiryStore,
    clock: Clock,
    settings: Settings,
    *,
    ask_log: AskLog | None = None,
    suggestions: SuggestionSource | None = None,
    graph: GraphStore | None = None,
) -> GenerateReport:
    """Run every generator whose dependency is wired; upsert through the dedupe."""
    drafts: list[InquiryItem] = []
    if ask_log is not None and settings.ask_log_enabled:
        drafts.extend(refused_questions(ask_log, clock, settings))
    if suggestions is not None:
        drafts.extend(undergrounded_terms(suggestions, clock, settings))
    if graph is not None:
        drafts.extend(low_evidence_relations(graph, clock, settings))
        drafts.extend(contradictions(graph, clock, settings))

    report = GenerateReport()
    for item in drafts:
        outcome = store.upsert_open(item)
        if outcome == "created":
            report.created += 1
            report.by_kind[item.kind] = report.by_kind.get(item.kind, 0) + 1
        elif outcome == "refreshed":
            report.refreshed += 1
        else:
            report.skipped_terminal += 1
    return report
