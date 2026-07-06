"""Draft a sugya page from one cluster (Prompt 41), reusing the compose pattern.

Sources → connections → open questions, every line grounded in the cluster's own
passages and cited by [S#]. Honest gaps are allowed: a section may say the corpus does
not yet answer something. The draft is a PROPOSAL — it indexes nothing; approval does.
Because the citable block is built ONLY from the cluster's refs, a page can only ever
cite its own cluster (`extract_cited_refs` filters to the numbered sources).
"""

from __future__ import annotations

import json
import re
from typing import get_args

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from maayan.clock import Clock
from maayan.consolidate.models import Cluster, SugyaPage, SugyaSection
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.generate.base import GenerationBackend, Message
from maayan.generate.rag import build_context, extract_cited_refs
from maayan.graph.models import RelationType, endpoint_key
from maayan.graph.store import GraphStore
from maayan.retrieve.models import SearchResult

_JSON_BLOB = re.compile(r"\{.*\}", re.DOTALL)
_KNOWN_REL_TYPES = frozenset(get_args(RelationType))

SUGYA_DRAFT_SYSTEM_PROMPT = (
    "You are a careful maggid shiur consolidating a sugya in chassidus and Kabbalah "
    "(p'nimiyus haTorah). You are given the numbered SOURCES of one topic cluster and a "
    "list of the approved CONNECTIONS among them. Write a curated sugya page as JSON:\n"
    '  {"title": "<short Hebrew title>", "sections": [\n'
    '     {"title": "מקורות", "body": "<what the sources say, each claim cited [S#]>"},\n'
    '     {"title": "קשרים", "body": "<how they relate, per the connections, cited [S#]>"},\n'
    '     {"title": "שאלות פתוחות", "body": "<what the cluster leaves open — an honest gap '
    'is fine>"}]}\n'
    "Rules:\n"
    "1. Use ONLY what the SOURCES say; add no outside facts and invent no mekoros.\n"
    "2. Cite every claim by its [S#] tag. If a section has nothing grounded to say, say so "
    "plainly rather than forcing it.\n"
    "3. Reply with ONE JSON object and nothing else."
)


class _DraftedSection(BaseModel):
    title: str = ""
    body: str = ""


class _DraftReply(BaseModel):
    title: str = ""
    sections: list[_DraftedSection] = Field(default_factory=list)


_REPLY = TypeAdapter[_DraftReply](_DraftReply)


class SugyaDrafter:
    """Draft a grounded, cited sugya page for a cluster (DI seam for the model)."""

    def __init__(
        self,
        backend: GenerationBackend,
        chunks: ChunkStore,
        graph: GraphStore,
        clock: Clock,
        *,
        model: str,
        system_prompt: str = SUGYA_DRAFT_SYSTEM_PROMPT,
    ) -> None:
        self._backend = backend
        self._chunks = chunks
        self._graph = graph
        self._clock = clock
        self._model = model
        self._system_prompt = system_prompt

    def draft(self, cluster: Cluster, *, author: str) -> SugyaPage:
        """Draft one proposed sugya page from `cluster`; cites only the cluster's refs."""
        sources = self._sources(cluster)
        reply = self._backend.generate(
            self._system_prompt,
            [Message(role="user", content=self._user_content(cluster, sources))],
        )
        parsed = _parse_reply(reply)
        sections: list[SugyaSection] = []
        for drafted in parsed.sections:
            body = drafted.body.strip()
            if not body:
                continue
            sections.append(
                SugyaSection(
                    title=drafted.title.strip() or "—",
                    body=body,
                    cited_refs=extract_cited_refs(body, sources),
                )
            )
        title = parsed.title.strip() or (cluster.concept or "סוגיא")
        return SugyaPage.make(
            page_key=cluster.key,
            concept=cluster.concept,
            title=title,
            sections=sections,
            author=author,
            created_at=self._clock.now(),
            model=self._model,
        )

    # -- internals ---------------------------------------------------------------
    def _sources(self, cluster: Cluster) -> list[SearchResult]:
        """The cluster's passages as a citable block (Hebrew preferred), in ref order."""
        results: list[SearchResult] = []
        for ref in cluster.refs:
            chunk = _preferred(self._chunks.get_by_ref(ref, include_retracted=False))
            if chunk is not None:
                results.append(
                    SearchResult(
                        ref=chunk.ref, text=chunk.text, score=0.0,
                        lang=chunk.lang, source=chunk.source, payload={"ref": chunk.ref},
                    )
                )
        return results

    def _user_content(self, cluster: Cluster, sources: list[SearchResult]) -> str:
        return (
            f"{build_context(sources)}\n\n"
            f"APPROVED CONNECTIONS:\n{self._connections_block(cluster)}\n\n"
            "Write the sugya page now, as the single JSON object described."
        )

    def _connections_block(self, cluster: Cluster) -> str:
        lines: list[str] = []
        for relation_id in cluster.relation_ids:
            relation = self._graph.get_relation(relation_id)
            if relation is None or relation.rel_type not in _KNOWN_REL_TYPES:
                continue
            s_kind, s_value = endpoint_key(relation.subject)
            o_kind, o_value = endpoint_key(relation.object)
            lines.append(f"- {s_value} —{relation.rel_type}→ {o_value} ({relation.author})")
        return "\n".join(lines) or "(none)"


def _preferred(chunks: list[Chunk]) -> Chunk | None:
    for chunk in chunks:
        if chunk.lang == "he":
            return chunk
    return chunks[0] if chunks else None


def _parse_reply(reply: str) -> _DraftReply:
    blob = _JSON_BLOB.search(reply)
    if blob is None:
        return _DraftReply()
    try:
        return _REPLY.validate_python(json.loads(blob.group(0)))
    except (json.JSONDecodeError, ValidationError):
        return _DraftReply()
