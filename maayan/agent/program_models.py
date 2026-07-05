"""Typed models for study programs (Prompt 40): the chavrusa run over a whole sefer.

A study program sweeps a book unit by unit and, per unit, has the drafting model
propose typed edges *from that unit* to the passages co-retrieved around it. Every
proposal is grounded (it must cite retrieved sources) and faithfulness-checked, and
the ones that pass land as **status="proposed"** relations — never approved. The gate
stays human: the inquiry queue (Prompt 37) rations the Rav's review of these
`derived_bootstrap` edges. Nothing here can index or approve anything.

The three tasks all draft through the one relation channel, differing only in the
allowed `rel_type`s and the prompt framing (a term usage and a mashal→nimshal are
both just typed edges the daf already implies):

  relations → explains / develops / parallels / connects / corresponds_to / argues_with / quotes
  terms     → defines / connects        (this unit uses/defines a term the source grounds)
  mashal    → is_mashal_for             (this unit is a mashal for the idea in the source)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ProgramTask = Literal["relations", "terms", "mashal"]
ProgramStatus = Literal["running", "paused", "done", "error"]

# Allowed rel_types per task — the subject is ALWAYS the unit being swept. Kept here
# (not in config) because it is schema: the shape the sweep is allowed to draft.
TASK_REL_TYPES: dict[ProgramTask, tuple[str, ...]] = {
    "relations": (
        "explains",
        "develops",
        "parallels",
        "connects",
        "corresponds_to",
        "argues_with",
        "quotes",
    ),
    "terms": ("defines", "connects"),
    "mashal": ("is_mashal_for",),
}


class ProgramCounts(BaseModel):
    """The funnel a program is judged by: how far each draft got, plus spend."""

    drafted: int = 0  # validated proposals (rel_type known + object resolved + grounded)
    passed_checks: int = 0  # of those, how many passed the faithfulness check
    queued: int = 0  # of those, how many landed as a NEW proposed relation
    model_calls: int = 0  # model calls spent (the "spend" line of the report)

    def add(self, other: ProgramCounts) -> None:
        """Accumulate another unit's counts into this running total (in place)."""
        self.drafted += other.drafted
        self.passed_checks += other.passed_checks
        self.queued += other.queued
        self.model_calls += other.model_calls


class ProgramUnit(BaseModel):
    """One unit of a sweep: a section of the book, addressed by its anchor ref."""

    index: int  # position in the book's canonical section order
    label: str
    ref: str


class RelationProposal(BaseModel):
    """One model-drafted candidate edge from a unit — pre-gate, pre-index.

    `subject_ref` is the unit; `object_ref` must be one of the co-retrieved sources
    (never an invented mekor). A proposal is `supported` only if it is grounded and
    the faithfulness pass flags nothing; `created` records whether persisting it made
    a NEW proposed relation (vs deduping onto an existing edge) — the queued signal.
    """

    subject_ref: str
    object_ref: str
    rel_type: str
    note: str = ""
    grounds: list[str] = Field(default_factory=list)  # grounding refs the note cites
    supported: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)
    created: bool = False


class UnitDraft(BaseModel):
    """The drafter's output for one unit: its proposals and what they cost."""

    proposals: list[RelationProposal] = Field(default_factory=list)
    model_calls: int = 0


class UnitResult(BaseModel):
    """The persisted, per-unit funnel — the rows of the report."""

    unit_index: int
    label: str
    ref: str
    counts: ProgramCounts


class StudyProgram(BaseModel):
    """A resumable sweep of one book with one task — the job's whole state.

    `cursor` is the next unit index to process, so a crash resumes exactly where it
    stopped. `author` is the program's provenance (e.g. ``program:<model>``): every
    edge it drafts carries it, and it is required — nothing anonymous enters the graph.
    """

    id: str
    book: str
    task: ProgramTask
    cursor: int = 0
    total_units: int = 0
    status: ProgramStatus = "running"
    counts: ProgramCounts = Field(default_factory=ProgramCounts)
    model: str = ""
    author: str
    started_at: datetime
    updated_at: datetime

    @field_validator("author")
    @classmethod
    def _author_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("author is required (a program's edges must be attributed)")
        return cleaned

    @classmethod
    def make(
        cls,
        *,
        book: str,
        task: ProgramTask,
        author: str,
        created_at: datetime,
        model: str = "",
        total_units: int = 0,
    ) -> StudyProgram:
        return cls(
            id=str(uuid.uuid4()),
            book=book,
            task=task,
            author=author,
            model=model,
            total_units=total_units,
            started_at=created_at,
            updated_at=created_at,
        )


class StudyProgramReport(BaseModel):
    """Everything `maayan study report` renders — the honest drafted/passed/queued funnel."""

    program: StudyProgram
    units: list[UnitResult] = Field(default_factory=list)
    evidence_histogram: dict[str, int] = Field(default_factory=dict)
