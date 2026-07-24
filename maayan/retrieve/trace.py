"""Typed trace of a single retrieval, for debugging "why did this answer/refuse?".

Retrieval normally reports only its final ranking plus one `relevance` number. When
that number is surprising there is nothing to look at: the dense branch, the sparse
(lexical) branch and the fusion are all collapsed before anyone sees them. These
models keep each stage separately so the whole decision is inspectable — the query
as actually sent, what each branch ranked, the absolute signals available to the
gate, and the answer/refuse call that followed.

Pure data (no Qdrant, no models), so the CLI, the UI and tests all render the same
object. `maayan/retrieve/inspect.py` produces it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from maayan.retrieve.models import SearchResult


class StageHit(BaseModel):
    """One ranked hit within a single retrieval stage."""

    rank: int  # 0-based, within this stage
    ref: str
    score: float
    book: str = ""
    source: str = ""


class StageTrace(BaseModel):
    """One stage's ranked output.

    `name` is the branch: "dense" (cosine), "sparse" (bge-m3 lexical weights),
    "fused" (RRF over both) or "rerank" (cross-encoder reordering of the fused pool).
    Comparing stages is the point: a ref high in `sparse` but absent from `dense`
    means the hit is lexical, and vice versa.
    """

    name: str
    hits: list[StageHit] = Field(default_factory=list)

    def rank_of(self, ref: str) -> int | None:
        """Rank of `ref` in this stage, or None if it did not appear."""
        for hit in self.hits:
            if hit.ref == ref:
                return hit.rank
        return None


class GateSignals(BaseModel):
    """The absolute relevance signals a refusal gate can be built from.

    All are computed over the same candidate pool. The `_top` values are the single
    best score in a branch; the `_mean` values average the pool, which is a much
    lower-variance estimate of "how much relevant material is actually there" — over
    ~9k points the single top cosine is a max over noise. `rerank_top` is present
    only when a cross-encoder ran.
    """

    dense_top: float = 0.0
    dense_mean: float = 0.0
    sparse_top: float = 0.0
    sparse_mean: float = 0.0
    rerank_top: float | None = None
    pool: int = 0  # how many hits the means were taken over


class QueryTrace(BaseModel):
    """One query variant exactly as sent to the index, with its per-branch rankings."""

    query: str
    stages: list[StageTrace] = Field(default_factory=list)
    signals: GateSignals = GateSignals()

    def stage(self, name: str) -> StageTrace | None:
        for st in self.stages:
            if st.name == name:
                return st
        return None


class RetrievalTrace(BaseModel):
    """Everything one `retrieve()` did, from question to answer/refuse decision.

    `queries` has one entry per query actually sent — more than one when query
    expansion is on, which is itself the thing worth seeing (the question the user
    asked is often not the string that was searched).
    """

    question: str
    queries: list[QueryTrace] = Field(default_factory=list)
    signals: GateSignals = GateSignals()  # aggregate across variants
    relevance: float = 0.0
    threshold: float = 0.0
    gate_signal: str = "dense_top"  # which signal `relevance` came from
    answered: bool = False
    results: list[SearchResult] = Field(default_factory=list)

    @property
    def decision(self) -> str:
        return "ANSWER" if self.answered else "REFUSE"


def format_trace(trace: RetrievalTrace, *, width: int = 58) -> str:
    """Render a trace as a plain-text report (CLI output; also handy in tests)."""
    lines = [f'question: "{trace.question}"']
    if len(trace.queries) > 1 or (trace.queries and trace.queries[0].query != trace.question):
        lines.append(f"expanded into {len(trace.queries)} quer(y/ies) actually sent:")
        for qt in trace.queries:
            lines.append(f'  · "{qt.query}"')
    lines.append("")

    for qt in trace.queries:
        if len(trace.queries) > 1:
            lines.append(f'--- query: "{qt.query}" ---')
        for stage in qt.stages:
            lines.append(f"  [{stage.name}]")
            if not stage.hits:
                lines.append("      (no hits)")
            for hit in stage.hits:
                marks = "".join(
                    other.name[0] if other.rank_of(hit.ref) is not None else "·"
                    for other in qt.stages
                    if other.name != stage.name
                )
                lines.append(
                    f"    {hit.rank + 1:>2}. {hit.score:>8.4f}  {marks:<4} "
                    f"{hit.ref[:width]}"
                )
        s = qt.signals
        lines.append(
            f"  signals: dense_top={s.dense_top:.4f} dense_mean@{s.pool}={s.dense_mean:.4f}  "
            f"sparse_top={s.sparse_top:.4f} sparse_mean@{s.pool}={s.sparse_mean:.4f}"
            + (f"  rerank_top={s.rerank_top:.4f}" if s.rerank_top is not None else "")
        )
        lines.append("")

    lines.append(
        f"GATE: {trace.decision} — {trace.gate_signal}={trace.relevance:.4f} "
        f"{'≥' if trace.answered else '<'} threshold={trace.threshold:.4f}"
    )
    lines.append(
        "  (marks column: which OTHER stages also contain this ref — "
        "d=dense s=sparse f=fused r=rerank, · = absent)"
    )
    return "\n".join(lines)
