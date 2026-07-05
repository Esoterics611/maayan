"""Deterministic clustering of approved knowledge (Prompt 41) — no model in the loop.

Connected components over approved graph edges: two refs land in the same cluster when
an approved relation chains them (directly or transitively). A component that also
touches a Concept endpoint is anchored on that concept. Components below the configured
minimum size are dropped. Everything is sorted, so the same graph always yields the same
clusters — determinism the tests rely on and the gate depends on.
"""

from __future__ import annotations

from maayan.consolidate.models import Cluster
from maayan.corpus.store import ChunkStore
from maayan.graph.models import endpoint_key
from maayan.graph.store import GraphStore

# Only human/derived knowledge consolidates — printed text is not "a contribution".
_CLUSTERABLE_SOURCES = frozenset({"expert", "derived", "term"})


class _UnionFind:
    """Tiny union-find over string node keys (deterministic; path-compressed)."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, node: str) -> None:
        self._parent.setdefault(node, node)

    def find(self, node: str) -> str:
        self.add(node)
        root = node
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[node] != root:
            self._parent[node], node = root, self._parent[node]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Deterministic parent choice (lexicographically smaller wins).
            lo, hi = sorted((ra, rb))
            self._parent[hi] = lo

    def roots(self) -> set[str]:
        return {self.find(node) for node in self._parent}


def _node(kind: str, value: str) -> str:
    return f"{kind}:{value}"


def build_clusters(
    graph: GraphStore, chunks: ChunkStore, *, min_size: int = 2
) -> list[Cluster]:
    """Group approved edges into clusters (connected components ≥ `min_size` refs)."""
    relations = graph.list_relations(status="approved")
    uf = _UnionFind()
    for relation in relations:
        s_kind, s_value = endpoint_key(relation.subject)
        o_kind, o_value = endpoint_key(relation.object)
        uf.union(_node(s_kind, s_value), _node(o_kind, o_value))

    # Collect the ref/concept members and the relations of each component root.
    ref_members: dict[str, set[str]] = {}
    concept_members: dict[str, set[str]] = {}
    relation_members: dict[str, list[str]] = {}
    for relation in relations:
        s_kind, s_value = endpoint_key(relation.subject)
        root = uf.find(_node(s_kind, s_value))
        relation_members.setdefault(root, []).append(relation.id)
        for kind, value in (endpoint_key(relation.subject), endpoint_key(relation.object)):
            if kind == "ref":
                ref_members.setdefault(root, set()).add(value)
            else:
                concept_members.setdefault(root, set()).add(value)

    # Chunk ids per ref, so a cluster carries the expert/derived chunks it distills.
    chunks_by_ref: dict[str, list[str]] = {}
    for source in _CLUSTERABLE_SOURCES:
        for chunk in chunks.get_chunks(source=source):
            chunks_by_ref.setdefault(chunk.ref, []).append(chunk.id)

    clusters: list[Cluster] = []
    for root in uf.roots():
        refs = sorted(ref_members.get(root, set()))
        if len(refs) < min_size:
            continue
        concept = _resolve_concept(graph, sorted(concept_members.get(root, set())))
        chunk_ids = sorted(
            cid for ref in refs for cid in chunks_by_ref.get(ref, [])
        )
        clusters.append(
            Cluster(
                concept=concept,
                refs=refs,
                relation_ids=sorted(relation_members.get(root, [])),
                chunk_ids=chunk_ids,
            )
        )
    clusters.sort(key=lambda c: c.key)
    return clusters


def find_cluster(
    graph: GraphStore, chunks: ChunkStore, *, concept: str, min_size: int = 2
) -> Cluster | None:
    """The cluster anchored on `concept` (its canonical or id), if one exists."""
    target = concept.strip()
    for cluster in build_clusters(graph, chunks, min_size=min_size):
        if cluster.concept is not None and cluster.concept == target:
            return cluster
    return None


def _resolve_concept(graph: GraphStore, concept_ids: list[str]) -> str | None:
    """Canonical name of the component's anchor concept (first, sorted), if any."""
    for concept_id in concept_ids:
        concept = graph.get_concept(concept_id)
        if concept is not None:
            return concept.canonical
    return None
