"""Typed health report — the boundary type for "is this thing actually working?".

Distinct from `Stats`, which counts what is IN the knowledge base. This answers
whether the parts that make it usable are reachable right now: the vector store, the
embedder, the generation backend. When maayan runs unattended behind a tunnel, the
difference between "no results" and "Qdrant is down" is the whole diagnosis, and
until now nothing reported it — `/healthz` returns a static `{"status": "ok"}`,
which is a liveness probe for the process, not for the stack.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "degraded", "down", "skipped"]


class ComponentHealth(BaseModel):
    """One dependency's state.

    `degraded` means reachable but not right — e.g. Qdrant answers but the collection
    is missing or empty, which retrieves nothing while looking perfectly healthy from
    a connection check. `skipped` means the check was deliberately not run (a probe
    that costs money or a model load), never that it passed.
    """

    name: str
    status: Status
    detail: str = ""
    latency_ms: float | None = None

    @property
    def ok(self) -> bool:
        return self.status in ("ok", "skipped")


class HealthReport(BaseModel):
    """Every component, plus the single question a monitor actually asks."""

    components: list[ComponentHealth] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.components)

    @property
    def status(self) -> Status:
        if any(c.status == "down" for c in self.components):
            return "down"
        if any(c.status == "degraded" for c in self.components):
            return "degraded"
        return "ok"

    def component(self, name: str) -> ComponentHealth | None:
        for c in self.components:
            if c.name == name:
                return c
        return None


def format_report(report: HealthReport) -> str:
    """Render the report as a small table (CLI output)."""
    glyph = {"ok": "✓", "degraded": "!", "down": "✗", "skipped": "–"}
    width = max((len(c.name) for c in report.components), default=4)
    lines = []
    for c in report.components:
        timing = f"{c.latency_ms:>7.0f}ms" if c.latency_ms is not None else " " * 9
        lines.append(
            f"  {glyph[c.status]} {c.name:<{width}} {c.status:<9}{timing}  {c.detail}"
        )
    lines.append("")
    lines.append(f"overall: {report.status.upper()}")
    return "\n".join(lines)
