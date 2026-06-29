"""Query expansion — turn one question into several retrieval queries.

A conceptual chassidus question rarely shares surface vocabulary with the sources
that answer it (Hebrew phrasing varies; the curated lexicon names ideas the question
only gestures at). Embedding the raw question once therefore under-retrieves. An
`QueryExpander` widens the net: it returns the original query plus reformulations,
which `MultiQueryRetriever` searches in parallel and fuses (RRF). Expansion only adds
*candidates* — the absolute relevance gate (default-deny) is unchanged.

Expanders compose:
- `NullExpander`     — passthrough (the default / off path).
- `LexiconExpander`  — deterministic, no model call: injects curated lexicon
                       vocabulary (canonical + related terms) when a registered term
                       appears in the query. Reuses the same fold-matching as the
                       lexicon itself (`corpus.normalize.fold_surface`).
- `LLMQueryExpander` — paraphrase/sub-aspect reformulations and an optional HyDE
                       (hypothetical-source) passage, via the injected
                       `GenerationBackend` (string→string; no protocol change).
- `CompositeExpander`— runs several expanders, dedupes (fold-insensitive), caps.

Everything is injected; counts/toggles come from config, never hardcoded in logic.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from maayan.corpus.normalize import fold_surface
from maayan.generate.base import GenerationBackend, Message
from maayan.lexicon.models import Term


class ExpandedQuery(BaseModel):
    """A query and the retrieval queries derived from it (original always first)."""

    original: str
    queries: list[str]


@runtime_checkable
class QueryExpander(Protocol):
    """Turns a query into one or more retrieval queries (DI seam)."""

    def expand(self, query: str) -> ExpandedQuery:
        ...


@runtime_checkable
class TermSource(Protocol):
    """Minimal lexicon read interface the LexiconExpander depends on (DI seam)."""

    def list_terms(self) -> list[Term]:
        ...


# Strip list bullets / numbering an LLM tends to prepend to each reformulation.
_BULLET = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s*")

MULTI_QUERY_SYSTEM_PROMPT = (
    "You help search a corpus of chassidus and Kabbalah (p'nimiyus haTorah). "
    "Given a study question, write alternative search queries that would surface the "
    "relevant sources. Vary the wording and angle (synonyms, the underlying concept, "
    "related technical terms, Hebrew/English). Rules: output ONE query per line, no "
    "numbering or commentary; stay on the same topic; do not answer the question."
)

HYDE_SYSTEM_PROMPT = (
    "You help search a corpus of chassidus and Kabbalah (p'nimiyus haTorah). "
    "Given a study question, write a short, plausible passage (2-4 sentences) of the "
    "kind a source text might contain that would answer it — in the language of the "
    "question. This is a search aid, not an answer: do NOT add citations, and it is "
    "fine if some details are uncertain. Output only the passage."
)


def _clean_lines(text: str, *, limit: int) -> list[str]:
    """Parse an LLM list response into at most `limit` cleaned, non-empty lines."""
    out: list[str] = []
    for raw in text.splitlines():
        line = _BULLET.sub("", raw).strip()
        if line:
            out.append(line)
        if len(out) >= limit:
            break
    return out


def dedupe_queries(queries: Sequence[str], *, max_queries: int) -> list[str]:
    """Order-preserving dedupe (fold-insensitive), capped at `max_queries`."""
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = fold_surface(q)
        if key and key not in seen:
            seen.add(key)
            out.append(q)
        if len(out) >= max_queries:
            break
    return out


class NullExpander:
    """No expansion: the query is its own only retrieval query."""

    def expand(self, query: str) -> ExpandedQuery:
        return ExpandedQuery(original=query, queries=[query])


class LexiconExpander:
    """Deterministically inject curated lexicon vocabulary when a term is in the query.

    No model call. If a registered (non-retracted) term's surface form appears in the
    query, append one augmented query carrying that term's canonical form and related
    terms — so retrieval also surfaces the term's own chunk and texts that use it.
    """

    def __init__(self, terms: TermSource, *, min_form_len: int = 2) -> None:
        self._terms = terms
        self._min_form_len = min_form_len

    def expand(self, query: str) -> ExpandedQuery:
        folded_query = fold_surface(query)
        if not folded_query:
            return ExpandedQuery(original=query, queries=[query])

        additions: list[str] = []
        for term in self._terms.list_terms():
            if term.retracted:
                continue
            forms = term.surface_forms or [term.canonical]
            if any(self._matches(f, folded_query) for f in forms):
                additions.append(term.canonical)
                additions.extend(term.related_terms)

        queries = [query]
        if additions:
            queries.append(f"{query} {' '.join(additions)}")
        return ExpandedQuery(original=query, queries=queries)

    def _matches(self, form: str, folded_query: str) -> bool:
        folded = fold_surface(form)
        return len(folded) >= self._min_form_len and folded in folded_query


class LLMQueryExpander:
    """Reformulations (+ optional HyDE passage) via the injected generation backend."""

    def __init__(
        self,
        backend: GenerationBackend,
        *,
        variants: int = 3,
        hyde: bool = True,
        multi_query_system_prompt: str = MULTI_QUERY_SYSTEM_PROMPT,
        hyde_system_prompt: str = HYDE_SYSTEM_PROMPT,
    ) -> None:
        self._backend = backend
        self._variants = variants
        self._hyde = hyde
        self._mq_prompt = multi_query_system_prompt
        self._hyde_prompt = hyde_system_prompt

    def expand(self, query: str) -> ExpandedQuery:
        queries = [query]
        if self._variants > 0:
            reply = self._backend.generate(
                self._mq_prompt,
                [Message(role="user", content=f"Question: {query}")],
            )
            queries.extend(_clean_lines(reply, limit=self._variants))
        if self._hyde:
            passage = self._backend.generate(
                self._hyde_prompt,
                [Message(role="user", content=f"Question: {query}")],
            ).strip()
            if passage:
                queries.append(passage)
        return ExpandedQuery(original=query, queries=queries)


class CompositeExpander:
    """Run several expanders and merge their queries (original first), deduped + capped."""

    def __init__(self, expanders: Sequence[QueryExpander], *, max_queries: int = 6) -> None:
        self._expanders = list(expanders)
        self._max_queries = max(1, max_queries)

    def expand(self, query: str) -> ExpandedQuery:
        collected = [query]
        for expander in self._expanders:
            collected.extend(expander.expand(query).queries)
        return ExpandedQuery(
            original=query,
            queries=dedupe_queries(collected, max_queries=self._max_queries),
        )
