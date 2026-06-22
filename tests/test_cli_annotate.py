"""CLI `annotate` tests — focused on the --refs comma bug and provenance wiring.

The heavy CaptureService is mocked: refs CONTAIN commas, so we assert they survive
the CLI intact rather than getting shredded by a naive comma split.
"""

from __future__ import annotations

from datetime import UTC, datetime

import maayan.capture.factory as factory
from maayan.capture.models import Annotation
from maayan.cli import _parse_refs, app

# Two real refs that each contain commas — the exact case the old split broke.
REF_A = "Tanya, Part I; Likkutei Amarim 1:13"
REF_B = "Likutei Torah, Vayechi 1:2"


def test_parse_refs_keeps_commas_intact() -> None:
    # Repeatable --ref: verbatim, commas preserved.
    assert _parse_refs([REF_A, REF_B], "") == [REF_A, REF_B]
    # --refs split on " | " (a delimiter refs never contain), commas preserved.
    assert _parse_refs([], f"{REF_A} | {REF_B}") == [REF_A, REF_B]
    # Both sources combine; blanks dropped.
    assert _parse_refs([REF_A], f" {REF_B} | ") == [REF_A, REF_B]
    assert _parse_refs([], "") == []


class _FakeCapture:
    def __init__(self) -> None:
        self.last: dict[str, object] = {}

    def add_annotation(self, session_id: str, **kwargs: object) -> Annotation:
        self.last = {"session_id": session_id, **kwargs}
        return Annotation(
            id="cli-1", session_id=session_id, timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            author=str(kwargs["author"]), kind=str(kwargs["kind"]), body=str(kwargs["body"]),
            linked_refs=list(kwargs.get("linked_refs", []) or []),  # type: ignore[arg-type]
            move=kwargs.get("move"),  # type: ignore[arg-type]
            directive=kwargs.get("directive"),  # type: ignore[arg-type]
            opens_aspect=bool(kwargs.get("opens_aspect", False)),
        )


def _runner():
    from typer.testing import CliRunner

    return CliRunner()


def test_annotate_repeatable_ref_round_trips_multicomma_refs(monkeypatch) -> None:
    fake = _FakeCapture()
    monkeypatch.setattr(factory, "build_capture_service", lambda *a, **k: fake)
    result = _runner().invoke(app, [
        "annotate", "--session", "s1", "--author", "R. Ginsburgh", "--body", "note",
        "--kind", "connection", "--ref", REF_A, "--ref", REF_B,
    ])
    assert result.exit_code == 0, result.output
    assert fake.last["linked_refs"] == [REF_A, REF_B]


def test_annotate_refs_blob_splits_on_pipe_not_comma(monkeypatch) -> None:
    fake = _FakeCapture()
    monkeypatch.setattr(factory, "build_capture_service", lambda *a, **k: fake)
    result = _runner().invoke(app, [
        "annotate", "--session", "s1", "--author", "R. G", "--body", "note",
        "--refs", f"{REF_A} | {REF_B}",
    ])
    assert result.exit_code == 0, result.output
    assert fake.last["linked_refs"] == [REF_A, REF_B]


def test_annotate_seed_passes_directive_and_opens_aspect(monkeypatch) -> None:
    fake = _FakeCapture()
    monkeypatch.setattr(factory, "build_capture_service", lambda *a, **k: fake)
    result = _runner().invoke(app, [
        "annotate", "--session", "s1", "--author", "R. G", "--body", "seed",
        "--opens-aspect", "--directive", "find the hint in Tanya",
    ])
    assert result.exit_code == 0, result.output
    assert fake.last["opens_aspect"] is True
    assert fake.last["directive"] == "find the hint in Tanya"


def test_annotate_requires_author() -> None:
    # No --author: Typer rejects the missing required option (non-zero exit).
    result = _runner().invoke(app, [
        "annotate", "--session", "s1", "--body", "note",
    ])
    assert result.exit_code != 0
