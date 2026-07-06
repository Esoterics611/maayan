"""Online backup of the SQLite knowledge layer — the irreplaceable capture data.

`data/maayan.sqlite3` holds everything the expert has taught (sessions, annotations,
seeds, developments, terms, the captured gold-set). It cannot be regenerated. This uses
SQLite's online backup API, so a copy is consistent even while the UI holds the database
open (a plain file copy of a live DB can capture a torn write). Config-driven directory
and retention; callable from the `maayan backup` CLI and cron-able on the deployed host.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


def backup_sqlite(
    db_path: str, backup_dir: str, *, keep: int = 14, now: datetime | None = None
) -> Path:
    """Write a consistent copy of ``db_path`` into ``backup_dir``; keep the newest ``keep``.

    Returns the path of the new timestamped backup. Raises ``FileNotFoundError`` if there
    is nothing to back up. ``now`` is injectable so the filename is deterministic in tests.
    """
    src = Path(db_path)
    if not src.exists():
        raise FileNotFoundError(f"No database to back up at {db_path!r}.")

    out_dir = Path(backup_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    dest = out_dir / f"{src.stem}-{stamp}.sqlite3"

    source = sqlite3.connect(str(src))
    try:
        target = sqlite3.connect(str(dest))
        try:
            source.backup(target)  # consistent snapshot even if `source` is being written
        finally:
            target.close()
    finally:
        source.close()

    _prune(out_dir, src.stem, keep)
    return dest


def _prune(out_dir: Path, stem: str, keep: int) -> None:
    """Delete all but the newest ``keep`` backups for this DB stem (timestamps sort by name)."""
    if keep <= 0:
        return
    backups = sorted(out_dir.glob(f"{stem}-*.sqlite3"), key=lambda p: p.name, reverse=True)
    for old in backups[keep:]:
        old.unlink(missing_ok=True)
