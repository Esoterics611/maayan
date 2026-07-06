"""Backup of the irreplaceable SQLite knowledge layer (online copy + retention)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from maayan.backup import backup_sqlite


def _make_db(path: Path, rows: int) -> None:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE t (id INTEGER, v TEXT)")
    con.executemany("INSERT INTO t VALUES (?, ?)", [(i, f"v{i}") for i in range(rows)])
    con.commit()
    con.close()


def test_backup_copies_data_consistently(tmp_path: Path) -> None:
    db = tmp_path / "maayan.sqlite3"
    _make_db(db, 5)

    dest = backup_sqlite(
        str(db), str(tmp_path / "backups"), now=datetime(2026, 7, 6, 12, 0, 0)
    )

    assert dest.exists()
    assert dest.name == "maayan-20260706-120000.sqlite3"
    con = sqlite3.connect(str(dest))
    assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 5  # data round-trips
    con.close()


def test_backup_prunes_to_keep(tmp_path: Path) -> None:
    db = tmp_path / "maayan.sqlite3"
    _make_db(db, 1)
    bdir = tmp_path / "backups"

    for sec in range(5):  # five distinct timestamps, retain only the newest 3
        backup_sqlite(str(db), str(bdir), keep=3, now=datetime(2026, 7, 6, 12, 0, sec))

    remaining = sorted(p.name for p in bdir.glob("maayan-*.sqlite3"))
    assert remaining == [
        "maayan-20260706-120002.sqlite3",
        "maayan-20260706-120003.sqlite3",
        "maayan-20260706-120004.sqlite3",
    ]


def test_backup_missing_db_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        backup_sqlite(str(tmp_path / "nope.sqlite3"), str(tmp_path / "b"))
