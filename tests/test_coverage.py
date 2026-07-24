"""Tests for the coverage audit — pure comparison logic, no network, no Qdrant."""

from __future__ import annotations

from maayan.index.coverage import build_report, format_report

STORED = {"Tanya": 697, "Torah Ohr, Miketz": 382}


def test_everything_reconciles_when_all_sides_agree() -> None:
    report = build_report(STORED, dict(STORED), expected=dict(STORED))
    assert report.ok
    assert report.problems == []
    assert report.total_stored == report.total_indexed == 1079
    assert all(r.index_delta == 0 and r.source_delta == 0 for r in report.rows)


def test_partial_index_is_flagged_per_book() -> None:
    # Qdrant has fewer points than the store: a half-finished re-index.
    report = build_report(STORED, {"Tanya": 500, "Torah Ohr, Miketz": 382})
    assert not report.ok
    assert [r.book for r in report.problems] == ["Tanya"]
    tanya = report.rows[0]
    assert tanya.index_delta == -197
    assert tanya.source_delta is None  # no independent count requested
    assert "MISMATCH" in format_report(report)


def test_partial_ingest_is_only_visible_against_the_source() -> None:
    # Store and index agree perfectly — but the ingest never fetched 97 segments.
    stored = {"Tanya": 600}
    report_offline = build_report(stored, dict(stored))
    assert report_offline.ok, "store/index agreement cannot see a missing ingest"

    report_remote = build_report(stored, dict(stored), expected={"Tanya": 697})
    assert not report_remote.ok
    assert report_remote.rows[0].source_delta == -97


def test_orphan_book_present_only_in_the_index_is_surfaced() -> None:
    # A rename or partial rebuild can leave points no chunk claims any more.
    report = build_report({"Tanya": 10}, {"Tanya": 10, "Stale Book": 42})
    assert not report.ok
    orphan = next(r for r in report.rows if r.book == "Stale Book")
    assert orphan.stored == 0 and orphan.index_delta == 42


def test_collection_total_counts_points_outside_the_listed_books() -> None:
    # total_indexed is the whole collection, so stray points still break `ok`
    # even when every listed book reconciles.
    report = build_report(STORED, dict(STORED), total_indexed=2000)
    assert report.problems == []
    assert not report.ok
    assert "re-run `maayan index`" in format_report(report)


def test_format_report_omits_the_source_column_when_offline() -> None:
    offline = format_report(build_report(STORED, dict(STORED)))
    assert "source" not in offline and "stored" in offline
    assert "OK — every book reconciles." in offline

    remote = format_report(build_report(STORED, dict(STORED), expected=dict(STORED)))
    assert "source" in remote
