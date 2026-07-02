"""Backfill: lift existing expert connection chunks into typed relations.

Today a connection lives as a prose chunk with an untyped `linked_refs` list in
its metadata. The backfill gives each one a structured twin: every pair of its
linked refs becomes one "connects" relation with the author preserved and
`source_chunk_id` pointing home. The prose chunk STAYS — the edge is an
additional, walkable view of the same knowledge, not a migration.

Status is "approved" directly (documented gate exception: these chunks already
passed the capture/faithfulness gate when they were created). Evidence encodes
who actually asserted them: a human author → "expert"; the free-model bootstrap
run (author "bootstrap:<model>") → "derived_bootstrap", so the unreviewed tier
stays visibly weaker and the inquiry queue (Prompt 37) can route it to the Rav.

Idempotent by construction: relation ids derive from (subject, object,
rel_type), so a rerun upserts the same rows and reports 0 created.
"""

from __future__ import annotations

from itertools import combinations

from maayan.clock import Clock
from maayan.config import Settings
from maayan.corpus.models import Chunk
from maayan.corpus.store import ChunkStore
from maayan.graph.models import BackfillResult, RefEndpoint, Relation
from maayan.graph.store import GraphStore

# Provenance convention from the free-model populate run (see POPULATE_REPORT):
# bootstrap-drafted contributions are attributed "bootstrap:<model-slug>".
BOOTSTRAP_AUTHOR_PREFIX = "bootstrap:"

# The chunk metadata kind that marks a connection contribution (capture loop).
CONNECTION_KIND = "connection"


def backfill_relations(
    chunk_store: ChunkStore,
    graph_store: GraphStore,
    clock: Clock,
    settings: Settings,
) -> BackfillResult:
    """Lift every live expert connection chunk into "connects" relations."""
    result = BackfillResult()
    for chunk in chunk_store.get_chunks(source="expert"):
        result.chunks_seen += 1
        refs = _linked_refs(chunk)
        if chunk.metadata.get("kind") != CONNECTION_KIND or len(refs) < 2:
            result.skipped_chunks += 1
            continue
        author = str(chunk.metadata.get("author", "")).strip()
        if not author:
            # Provenance is the point: an unattributed chunk cannot become an edge.
            result.skipped_chunks += 1
            continue
        result.connection_chunks += 1
        bootstrap = author.startswith(BOOTSTRAP_AUTHOR_PREFIX)
        for left, right in combinations(refs, 2):
            relation = Relation.make(
                subject=RefEndpoint(ref=left),
                object=RefEndpoint(ref=right),
                rel_type="connects",
                evidence="derived_bootstrap" if bootstrap else "expert",
                confidence=(
                    settings.graph_bootstrap_confidence
                    if bootstrap
                    else settings.graph_default_confidence
                ),
                status="approved",
                author=author,
                source_chunk_id=chunk.id,
                created_at=clock.now(),
            )
            if graph_store.get_relation(relation.id) is None:
                result.relations_created += 1
            else:
                result.relations_existing += 1
            graph_store.save_relation(relation)
    return result


def _linked_refs(chunk: Chunk) -> list[str]:
    """The chunk's linked refs, deduped, order preserved (pairs stay deterministic)."""
    raw = chunk.metadata.get("linked_refs")
    if not isinstance(raw, list):
        return []
    seen: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in seen:
            seen.append(text)
    return seen
