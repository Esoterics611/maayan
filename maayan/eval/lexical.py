"""Lexical recall: of the passages that provably contain a term, how many are found?

The question-based gold set measures whether retrieval finds *an* answer. It cannot
measure **recall of a term's actual discussion**, because nobody has enumerated every
passage where a term appears — and a term's treatment usually spans many passages, so
"top-1 was relevant" hides the fact that most of the material never surfaced.

This harness derives its ground truth from the corpus itself, so it needs no authored
content and cannot be wrong: a case is `term → every stored chunk whose text contains
that term`. Matching uses `fold_surface`, so a vocalized Tanya passage and a plain
Torah Ohr one both count (the nikkud/gershayim differences are exactly what R5 was
about). Recall@k against that set is an objective, reproducible number.

Cases are generated once and checked in, because a guard whose ground truth moves
with the corpus cannot detect a regression — see `select_cases`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from maayan.corpus.models import Chunk
from maayan.corpus.normalize import fold_surface
from maayan.eval.metrics import recall_at_k
from maayan.retrieve.retriever import Retrieving


class LexicalCase(BaseModel):
    """One term and every ref that provably contains it."""

    term: str
    expected_refs: list[str] = Field(default_factory=list)
    books: list[str] = Field(default_factory=list)  # which books it occurs in (context)

    @property
    def occurrences(self) -> int:
        return len(self.expected_refs)


class LexicalGoldset(BaseModel):
    """A checked-in set of lexical recall cases, plus how it was generated."""

    corpus_chunks: int = 0  # store size when generated — a mismatch means it is stale
    cases: list[LexicalCase] = Field(default_factory=list)


class LexicalCaseResult(BaseModel):
    """One term's outcome — kept so a regression names the term that broke."""

    term: str
    occurrences: int
    recall: dict[int, float] = Field(default_factory=dict)
    precision: dict[int, float] = Field(default_factory=dict)


class LexicalReport(BaseModel):
    """Precision@k and recall@k over the lexical cases, averaged across terms.

    BOTH are needed because the corpus is dense in its own vocabulary: "צמצום" occurs
    in 372 passages, so recall@10 is capped at 2.7% no matter how good retrieval is —
    that number measures k, not quality. Precision@k ("of the k passages returned for
    this term, how many actually contain it?") stays meaningful at any density and is
    the discriminative signal for common terms. Recall carries the rare ones, where
    finding the handful of real occurrences is the whole task.
    """

    n_cases: int = 0
    ks: list[int] = Field(default_factory=list)
    recall: dict[int, float] = Field(default_factory=dict)  # macro: mean over cases
    precision: dict[int, float] = Field(default_factory=dict)  # macro: mean over cases
    found: dict[int, int] = Field(default_factory=dict)  # micro: refs found in total
    total_occurrences: int = 0
    per_case: list[LexicalCaseResult] = Field(default_factory=list)


def find_occurrences(chunks: Sequence[Chunk], term: str) -> list[str]:
    """Refs of every chunk containing `term`, matched on folded surface forms."""
    needle = fold_surface(term)
    if not needle:
        return []
    return sorted(c.ref for c in chunks if needle in fold_surface(c.text))


def select_cases(
    chunks: Sequence[Chunk],
    terms: Sequence[str],
    *,
    min_occurrences: int = 3,
    max_occurrences: int = 40,
) -> list[LexicalCase]:
    """Build cases for terms whose occurrence count is informative.

    Terms are skipped at both ends on purpose. Below `min_occurrences` recall@k is a
    coin flip on one or two chunks; above `max_occurrences` the term is so common that
    no top-k could contain its occurrences and the metric would measure k, not quality.
    """
    by_ref = {c.ref: c for c in chunks}
    cases: list[LexicalCase] = []
    for term in terms:
        refs = find_occurrences(chunks, term)
        if not (min_occurrences <= len(refs) <= max_occurrences):
            continue
        cases.append(
            LexicalCase(
                term=term,
                expected_refs=refs,
                books=sorted({by_ref[r].book for r in refs}),
            )
        )
    return cases


def run_lexical_eval(
    retriever: Retrieving, cases: Sequence[LexicalCase], ks: Sequence[int]
) -> LexicalReport:
    """Retrieve each term and score recall@k against its known occurrences."""
    ks = sorted(ks)
    max_k = max(ks) if ks else 10
    macro_recall = {k: 0.0 for k in ks}
    macro_precision = {k: 0.0 for k in ks}
    micro = {k: 0 for k in ks}
    per_case: list[LexicalCaseResult] = []
    total = 0
    for case in cases:
        retrieved = [r.ref for r in retriever.retrieve(case.term, k=max_k).results]
        expected = set(case.expected_refs)
        case_recall = {k: recall_at_k(retrieved, case.expected_refs, k) for k in ks}
        case_precision = {k: _precision_at_k(retrieved, expected, k) for k in ks}
        for k in ks:
            macro_recall[k] += case_recall[k]
            macro_precision[k] += case_precision[k]
            micro[k] += sum(1 for r in retrieved[:k] if r in expected)
        total += case.occurrences
        per_case.append(
            LexicalCaseResult(
                term=case.term, occurrences=case.occurrences,
                recall=case_recall, precision=case_precision,
            )
        )
    n = len(cases) or 1
    return LexicalReport(
        n_cases=len(cases),
        ks=list(ks),
        recall={k: macro_recall[k] / n for k in ks},
        precision={k: macro_precision[k] / n for k in ks},
        found=micro,
        total_occurrences=total,
        per_case=per_case,
    )


def _precision_at_k(retrieved: Sequence[str], expected: set[str], k: int) -> float:
    """Fraction of the top-k that actually contain the term (0.0 if nothing returned)."""
    top = retrieved[:k]
    if not top:
        return 0.0
    return sum(1 for r in top if r in expected) / len(top)


def format_lexical_report(report: LexicalReport, *, worst: int = 10) -> str:
    """Render the report, listing the worst-recall terms (where the misses are)."""
    lines = [
        f"Lexical recall: {report.n_cases} terms, "
        f"{report.total_occurrences} known occurrences",
        "",
        f"{'k':>4} | {'precision@k':>12} | {'recall@k':>9}",
        "-" * 32,
    ]
    for k in report.ks:
        lines.append(
            f"{k:>4} | {report.precision.get(k, 0.0):>12.3f} | "
            f"{report.recall.get(k, 0.0):>9.3f}"
        )
    lines.append("")
    lines.append(
        "precision@k is the guard: recall is capped by k for terms with hundreds of "
        "occurrences, so a low recall there is arithmetic, not a defect."
    )
    if report.per_case and report.ks:
        top_k = report.ks[-1]
        ranked = sorted(report.per_case, key=lambda c: c.precision.get(top_k, 0.0))
        lines.append("")
        lines.append(f"worst precision@{top_k}:")
        for case in ranked[:worst]:
            lines.append(
                f"  p={case.precision.get(top_k, 0.0):>5.2f}  "
                f"r={case.recall.get(top_k, 0.0):>5.2f}  {case.term}  "
                f"({case.occurrences} occurrences)"
            )
    return "\n".join(lines)


def load_lexical_goldset(path: str) -> LexicalGoldset:
    """Load a generated lexical gold set from YAML or JSON."""
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) if p.suffix in (".yaml", ".yml") else json.loads(raw)
    return LexicalGoldset.model_validate(data)


def save_lexical_goldset(goldset: LexicalGoldset, path: str) -> None:
    """Write a generated lexical gold set as YAML (deterministic ordering)."""
    Path(path).write_text(
        "# GENERATED by `maayan eval --lexical --rebuild` — do not hand-edit.\n"
        "# Ground truth is derived from the corpus: expected_refs are every stored\n"
        "# chunk whose text contains the term. Regenerate after a corpus change.\n"
        + yaml.safe_dump(
            goldset.model_dump(), allow_unicode=True, sort_keys=False, width=1000
        ),
        encoding="utf-8",
    )
