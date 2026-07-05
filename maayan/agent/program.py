"""The study-program runner (Prompt 40): sweep a sefer, unit by unit, into the gates.

This is the machine that converts model-hours into *proposed* knowledge at corpus
scale. It reuses the populate drip (`maayan.populate.drip.run_drip`) for pacing,
backoff, and resumability — there is no second job engine here. Per unit it asks the
drafter for grounded, faithfulness-checked edge proposals and persists the supported
ones as **status="proposed"** relations (evidence ``derived_bootstrap``). Nothing is
auto-approved: the gate stays human, and the inquiry queue ranks these edges for the
Rav. A crash resumes from the persisted cursor; ``--units N`` samples.
"""

from __future__ import annotations

from typing import cast

from maayan.agent.program_drafter import ProgramDrafter
from maayan.agent.program_models import (
    ProgramCounts,
    ProgramTask,
    ProgramUnit,
    RelationProposal,
    StudyProgram,
    StudyProgramReport,
    UnitResult,
)
from maayan.agent.program_store import ProgramStore
from maayan.clock import Clock
from maayan.corpus.store import ChunkStore
from maayan.graph.models import RefEndpoint, Relation, RelationType
from maayan.graph.store import GraphStore
from maayan.populate.drip import run_drip


class StudyProgramRunner:
    """Create + run + report on study programs; every collaborator injected."""

    def __init__(
        self,
        drafter: ProgramDrafter,
        chunks: ChunkStore,
        graph: GraphStore,
        store: ProgramStore,
        clock: Clock,
        *,
        pace: float,
        bootstrap_confidence: float,
        max_retries: int = 5,
        backoff: float = 30.0,
    ) -> None:
        self._drafter = drafter
        self._chunks = chunks
        self._graph = graph
        self._store = store
        self._clock = clock
        self._pace = pace
        self._bootstrap_confidence = bootstrap_confidence
        self._max_retries = max_retries
        self._backoff = backoff

    def enumerate_units(self, book: str) -> list[ProgramUnit]:
        """The book's sections in canonical order — the sweep's units."""
        return [
            ProgramUnit(index=i, label=label, ref=ref)
            for i, (label, ref, _lang) in enumerate(self._chunks.list_sections(book))
            if ref
        ]

    def create(
        self, *, book: str, task: ProgramTask, author: str, model: str = ""
    ) -> StudyProgram:
        """Register a new program over `book` (cursor 0), persisted and ready to run."""
        program = StudyProgram.make(
            book=book,
            task=task,
            author=author,
            model=model,
            created_at=self._clock.now(),
            total_units=len(self.enumerate_units(book)),
        )
        return self._store.save_program(program)

    async def run(self, program: StudyProgram, *, units: int | None = None) -> StudyProgram:
        """Process units from the cursor (paced, resumable); return the updated program.

        `units` caps how many units this invocation processes (sampling / cost). The
        cursor advances and the program is saved after EACH unit, so a crash resumes at
        the next unit with no double work (persistence is idempotent).
        """
        all_units = self.enumerate_units(program.book)
        program.total_units = len(all_units)
        start = program.cursor
        end = len(all_units) if units is None else min(len(all_units), start + units)
        todo = all_units[start:end]

        program.status = "running"
        program.updated_at = self._clock.now()
        self._store.save_program(program)

        def draft_one(unit: ProgramUnit) -> list[RelationProposal]:
            draft = self._drafter.draft_unit(unit.ref, program.task)
            counts = ProgramCounts(model_calls=draft.model_calls)
            for proposal in draft.proposals:
                counts.drafted += 1
                if proposal.supported:
                    counts.passed_checks += 1
                    if self._persist(program, proposal):
                        counts.queued += 1
            self._store.save_unit_result(
                program.id,
                UnitResult(
                    unit_index=unit.index, label=unit.label, ref=unit.ref, counts=counts
                ),
            )
            program.counts.add(counts)
            program.cursor = unit.index + 1
            program.updated_at = self._clock.now()
            self._store.save_program(program)
            return draft.proposals

        await run_drip(
            todo,
            draft_one,
            clock=self._clock,
            pace=self._pace,
            max_retries=self._max_retries,
            backoff=self._backoff,
        )

        program.status = "done" if program.cursor >= len(all_units) else "paused"
        program.updated_at = self._clock.now()
        self._store.save_program(program)
        return program

    def build_report(self, program_id: str) -> StudyProgramReport:
        """Assemble the funnel report: per-unit rows + the program's evidence histogram."""
        program = self._store.get_program(program_id)
        if program is None:
            raise ValueError(f"No study program with id {program_id!r}.")
        histogram: dict[str, int] = {}
        for relation in self._graph.list_relations(status="proposed"):
            if relation.author == program.author:
                histogram[relation.evidence] = histogram.get(relation.evidence, 0) + 1
        return StudyProgramReport(
            program=program,
            units=self._store.unit_results(program_id),
            evidence_histogram=histogram,
        )

    # -- persistence -------------------------------------------------------------
    def _persist(self, program: StudyProgram, proposal: RelationProposal) -> bool:
        """Save one supported proposal as a *proposed* relation. Returns True if NEW.

        Evidence is ``derived_bootstrap`` (model-drafted, not yet human-reviewed) and
        status is ``proposed`` — the gate is untouched. Deterministic ids mean a
        re-run dedupes rather than duplicating, and the store never downgrades a
        stronger existing edge.
        """
        relation = Relation.make(
            subject=RefEndpoint(ref=proposal.subject_ref),
            object=RefEndpoint(ref=proposal.object_ref),
            rel_type=cast("RelationType", proposal.rel_type),
            evidence="derived_bootstrap",
            confidence=self._bootstrap_confidence,
            status="proposed",
            author=program.author,
            note=proposal.note or None,
            created_at=self._clock.now(),
        )
        created = self._graph.get_relation(relation.id) is None
        self._graph.save_relation(relation)
        proposal.created = created
        return created


def render_report_markdown(report: StudyProgramReport) -> str:
    """POPULATE_REPORT-style markdown — the document the production run is judged by."""
    p = report.program
    c = p.counts
    lines = [
        f"# Study program report — {p.book}",
        "",
        f"- **Program id:** `{p.id}`",
        f"- **Task:** {p.task}",
        f"- **Drafter:** {p.model or '(generation model)'}  ·  **Author:** {p.author}",
        f"- **Progress:** {p.cursor}/{p.total_units} units  ·  **Status:** {p.status}",
        "",
        "## Funnel",
        "",
        "| drafted | passed checks | queued (proposed) | model calls |",
        "|---:|---:|---:|---:|",
        f"| {c.drafted} | {c.passed_checks} | {c.queued} | {c.model_calls} |",
        "",
        "## Evidence histogram (this program's proposed edges)",
        "",
    ]
    if report.evidence_histogram:
        for evidence, n in sorted(report.evidence_histogram.items()):
            lines.append(f"- {evidence}: {n}")
    else:
        lines.append("- (none yet)")
    lines += [
        "",
        "## Per unit",
        "",
        "| # | unit | drafted | passed | queued | calls |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for unit in report.units:
        uc = unit.counts
        lines.append(
            f"| {unit.unit_index} | {unit.label or unit.ref} | {uc.drafted} | "
            f"{uc.passed_checks} | {uc.queued} | {uc.model_calls} |"
        )
    lines.append("")
    return "\n".join(lines)
