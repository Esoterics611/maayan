"""Coverage audit: is everything that should be retrievable actually in the index?

A silent partial ingest or a half-finished re-index degrades retrieval in the most
confusing possible way — the system does not error, it just quietly cannot find some
of the corpus, and every downstream metric absorbs the loss as "bad retrieval". The
only way to catch it is to count the same thing three ways and require agreement:

    stored   — live (non-retracted) chunks in the SQLite knowledge layer
    indexed  — points actually present in the Qdrant collection
    expected — an INDEPENDENT count from the upstream source (opt-in; needs network)

`stored` vs `indexed` is the everyday guard and is fully offline. `expected` is the
stronger claim — it catches an ingest that never fetched a chapter at all, which the
first check cannot see because the chunk was never written either.

Pure comparison logic lives here (no network, no Qdrant); callers inject the counts.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, Field


class CoverageRow(BaseModel):
    """Coverage for one book: the same corpus counted from each side."""

    book: str
    stored: int = 0
    indexed: int = 0
    expected: int | None = None  # None when no independent count was requested/available

    @property
    def index_delta(self) -> int:
        """indexed − stored. Negative = points missing from Qdrant; positive = orphans."""
        return self.indexed - self.stored

    @property
    def source_delta(self) -> int | None:
        """stored − expected. Negative = the ingest never fetched some of the source."""
        return None if self.expected is None else self.stored - self.expected

    @property
    def ok(self) -> bool:
        return self.index_delta == 0 and self.source_delta in (None, 0)


class CoverageReport(BaseModel):
    """Per-book coverage plus the collection-wide totals."""

    rows: list[CoverageRow] = Field(default_factory=list)
    total_stored: int = 0
    total_indexed: int = 0  # the collection's point count, incl. books not listed

    @property
    def problems(self) -> list[CoverageRow]:
        return [r for r in self.rows if not r.ok]

    @property
    def ok(self) -> bool:
        return not self.problems and self.total_indexed == self.total_stored


def build_report(
    stored: Mapping[str, int],
    indexed: Mapping[str, int],
    *,
    expected: Mapping[str, int] | None = None,
    total_indexed: int | None = None,
) -> CoverageReport:
    """Compare per-book counts from the store, the index and (optionally) the source.

    Books present on any side appear in the report, so a book that exists ONLY in
    Qdrant (an orphan left by a rename or a partial rebuild) is still surfaced.
    """
    expected = expected or {}
    books = sorted(set(stored) | set(indexed) | set(expected))
    rows = [
        CoverageRow(
            book=b,
            stored=stored.get(b, 0),
            indexed=indexed.get(b, 0),
            expected=expected.get(b) if b in expected else None,
        )
        for b in books
    ]
    total_stored = sum(stored.values())
    return CoverageReport(
        rows=rows,
        total_stored=total_stored,
        total_indexed=sum(indexed.values()) if total_indexed is None else total_indexed,
    )


def format_report(report: CoverageReport) -> str:
    """Render the report as a table, flagging every book that does not reconcile."""
    width = max((len(r.book) for r in report.rows), default=4)
    has_expected = any(r.expected is not None for r in report.rows)
    header = f"{'book':<{width}} | {'stored':>7} | {'indexed':>7} | {'Δidx':>5}"
    if has_expected:
        header += f" | {'source':>7} | {'Δsrc':>5}"
    lines = [header, "-" * len(header)]
    for r in report.rows:
        line = f"{r.book:<{width}} | {r.stored:>7} | {r.indexed:>7} | {r.index_delta:>+5}"
        if has_expected:
            exp = "     —" if r.expected is None else f"{r.expected:>7}"
            src = "    —" if r.source_delta is None else f"{r.source_delta:>+5}"
            line += f" | {exp} | {src}"
        lines.append(line + ("" if r.ok else "   <-- MISMATCH"))
    lines.append("-" * len(header))
    lines.append(f"stored total: {report.total_stored}   collection points: {report.total_indexed}")
    if report.ok:
        lines.append("OK — every book reconciles.")
    else:
        lines.append(f"{len(report.problems)} book(s) do not reconcile.")
        if report.total_indexed != report.total_stored:
            lines.append(
                f"collection point count ({report.total_indexed}) != stored "
                f"({report.total_stored}) — re-run `maayan index`."
            )
    return "\n".join(lines)
