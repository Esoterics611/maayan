"""The margins (Prompt 36): a daf apparatus for every source.

Standing on any passage, see everything the system knows AROUND it — the
Mesoras-HaShas pattern in software. Read-only composition of existing data (no
new write paths): approved graph edges grouped by type, lexicon terms whose
surface forms appear in the passage, the expert layer (expert/derived/term/
shiur/sugya chunks referencing the ref), and developments grounded on it.

An empty apparatus is a statement, not an error: an unknown or unannotated ref
returns the empty groups — silence is data.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field, computed_field

from maayan.corpus.models import Chunk
from maayan.corpus.normalize import fold_surface
from maayan.corpus.store import ChunkStore
from maayan.develop.store import DevelopmentStore
from maayan.graph.models import Endpoint, RefEndpoint, Relation, endpoint_str
from maayan.graph.store import GraphStore
from maayan.lexicon.models import Term

# Fixed group order — it encodes the system's values: pasuk anchors first, then
# the typed relations, exactly as the UI spec's margins layout reads.
APPARATUS_REL_ORDER: tuple[str, ...] = (
    "quotes_pasuk",
    "quotes",
    "parallels",
    "connects",
    "explains",
    "is_mashal_for",
    "corresponds_to",
    "argues_with",
    "develops",
    "defines",
)

# Layered-knowledge sources that can reference a printed ref (the expert layer).
LAYER_SOURCES: tuple[str, ...] = ("expert", "derived", "term", "shiur", "sugya")

# Metadata keys through which a layered chunk references printed refs.
_REF_KEYS: tuple[str, ...] = ("linked_refs", "grounded_in", "source_refs", "child_refs")

_SNIPPET_WIDTH = 100
# Same guard as LexiconExpander: 1-char folded forms match everything.
_MIN_FORM_LEN = 2


class TermReader(Protocol):
    """The one lexicon read the apparatus needs (DI seam; TermService satisfies it)."""

    def list_terms(self) -> list[Term]:
        ...


class RelationMarginItem(BaseModel):
    """One edge in the margins: full provenance + the far side, resolved if local."""

    relation: Relation
    far: Endpoint
    far_label: str  # the ref string / concept name shown in the margin
    far_snippet: str | None = None  # first line, when the far side is a live chunk
    in_corpus: bool = False  # False → an anchor outside the corpus (still real)


class RelationMarginGroup(BaseModel):
    rel_type: str
    items: list[RelationMarginItem]


class TermMarginItem(BaseModel):
    term_id: str
    canonical: str
    term_type: str
    author: str


class LayerMarginItem(BaseModel):
    """One expert-layer chunk that references this ref."""

    chunk_id: str
    ref: str
    source: str  # expert | derived | term | shiur | sugya
    author: str | None = None
    kind: str | None = None
    snippet: str


class DevelopmentMarginItem(BaseModel):
    development_id: str
    author: str
    status: str
    snippet: str


class Apparatus(BaseModel):
    """Everything the beis medrash knows about one ref, grouped like a daf."""

    ref: str
    in_corpus: bool
    relation_groups: list[RelationMarginGroup] = Field(default_factory=list)
    terms: list[TermMarginItem] = Field(default_factory=list)
    expert_layer: list[LayerMarginItem] = Field(default_factory=list)
    developments: list[DevelopmentMarginItem] = Field(default_factory=list)

    # mypy can't see through @computed_field-on-@property yet (pydantic-docs
    # sanctioned ignore); serialized because the UI count badge needs it.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        """The count badge on the collapsed affordance (גליון · 7)."""
        return (
            sum(len(g.items) for g in self.relation_groups)
            + len(self.terms)
            + len(self.expert_layer)
            + len(self.developments)
        )


class ApparatusService:
    """Assemble the margins for a canonical ref. Injected stores; read-only."""

    def __init__(
        self,
        chunks: ChunkStore,
        graph: GraphStore,
        terms: TermReader,
        developments: DevelopmentStore,
    ) -> None:
        self._chunks = chunks
        self._graph = graph
        self._terms = terms
        self._developments = developments

    def assemble(self, ref: str) -> Apparatus:
        passage_chunks = self._chunks.get_by_ref(ref, include_retracted=False)
        return Apparatus(
            ref=ref,
            in_corpus=bool(passage_chunks),
            relation_groups=self._relation_groups(ref),
            terms=self._terms_in(passage_chunks),
            expert_layer=self._expert_layer(ref),
            developments=self._developments_on(ref),
        )

    # -- groups ------------------------------------------------------------------
    def _relation_groups(self, ref: str) -> list[RelationMarginGroup]:
        """Approved edges touching the ref, grouped by type in the fixed order."""
        by_type: dict[str, list[RelationMarginItem]] = {}
        for relation in self._graph.relations_for(RefEndpoint(ref=ref), status="approved"):
            far = (
                relation.object
                if isinstance(relation.subject, RefEndpoint) and relation.subject.ref == ref
                else relation.subject
            )
            item = RelationMarginItem(
                relation=relation, far=far, far_label=endpoint_str(far)
            )
            if isinstance(far, RefEndpoint):
                far_chunk = self._preferred(
                    self._chunks.get_by_ref(far.ref, include_retracted=False)
                )
                if far_chunk is not None:
                    item.in_corpus = True
                    item.far_snippet = _snippet(far_chunk.text)
            by_type.setdefault(relation.rel_type, []).append(item)
        order = {t: i for i, t in enumerate(APPARATUS_REL_ORDER)}
        return [
            RelationMarginGroup(rel_type=rel_type, items=items)
            for rel_type, items in sorted(
                by_type.items(), key=lambda kv: order.get(kv[0], len(order))
            )
        ]

    def _terms_in(self, passage_chunks: list[Chunk]) -> list[TermMarginItem]:
        """Lexicon terms whose surface forms appear in the passage text.

        Reuses the lexicon's own matching (fold_surface containment, exactly as
        LexiconExpander matches terms in a query) — no new matcher.
        """
        folded_text = fold_surface(" ".join(c.text for c in passage_chunks))
        if not folded_text:
            return []
        found: list[TermMarginItem] = []
        for term in self._terms.list_terms():
            if term.retracted:
                continue
            forms = term.surface_forms or [term.canonical]
            if any(
                len(folded) >= _MIN_FORM_LEN and folded in folded_text
                for folded in (fold_surface(f) for f in forms)
            ):
                found.append(
                    TermMarginItem(
                        term_id=term.id,
                        canonical=term.canonical,
                        term_type=term.term_type,
                        author=term.author,
                    )
                )
        return found

    def _expert_layer(self, ref: str) -> list[LayerMarginItem]:
        """Layered chunks (expert/derived/term/shiur/sugya) that reference this ref."""
        items: list[LayerMarginItem] = []
        for source in LAYER_SOURCES:
            for chunk in self._chunks.get_chunks(source=source):
                if not _references(chunk, ref):
                    continue
                author = chunk.metadata.get("author")
                kind = chunk.metadata.get("kind")
                items.append(
                    LayerMarginItem(
                        chunk_id=chunk.id,
                        ref=chunk.ref,
                        source=source,
                        author=author if isinstance(author, str) else None,
                        kind=kind if isinstance(kind, str) else None,
                        snippet=_snippet(chunk.text),
                    )
                )
        return items

    def _developments_on(self, ref: str) -> list[DevelopmentMarginItem]:
        return [
            DevelopmentMarginItem(
                development_id=dev.id,
                author=dev.author,
                status=dev.status,
                snippet=_snippet(dev.text),
            )
            for dev in self._developments.list_developments()
            if ref in dev.grounded_in and dev.status == "approved"
        ]

    @staticmethod
    def _preferred(chunks: list[Chunk]) -> Chunk | None:
        """Hebrew first (the primary language of the interface), else whatever exists."""
        for chunk in chunks:
            if chunk.lang == "he":
                return chunk
        return chunks[0] if chunks else None


def _snippet(text: str) -> str:
    line = text.strip().splitlines()[0] if text.strip() else ""
    return line[:_SNIPPET_WIDTH]


def _references(chunk: Chunk, ref: str) -> bool:
    """Does this layered chunk point at `ref` through any of its metadata keys?"""
    for key in _REF_KEYS:
        value = chunk.metadata.get(key)
        if isinstance(value, list) and ref in value:
            return True
    parent = chunk.metadata.get("parent_ref")
    return isinstance(parent, str) and parent == ref
