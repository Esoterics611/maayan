"""SQLite persistence + ingestion for audio assets (same DB file as chunks).

`store_file` is idempotent by content hash (re-uploading the same audio returns the
existing row) and normalizes to mono 16 kHz via ffmpeg for Whisper. If ffmpeg is
missing the file is kept as-is with a warning, so the flow degrades instead of
breaking. Time + ids come from the injected `Clock` (house rule: no inline time).
"""

from __future__ import annotations

import contextlib
import hashlib
import shutil
import sqlite3
import subprocess
import uuid
import warnings
import wave
from datetime import datetime
from pathlib import Path

from maayan.audio.models import AudioAsset
from maayan.clock import Clock, SystemClock

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audio_assets (
    id          TEXT PRIMARY KEY,
    owner       TEXT NOT NULL,
    filename    TEXT NOT NULL,
    path        TEXT NOT NULL,
    duration_s  REAL,
    sample_rate INTEGER,
    sha256      TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audio_sha256 ON audio_assets(sha256);
"""


def _wav_meta(path: Path) -> tuple[float | None, int | None]:
    """(duration_s, sample_rate) for a readable WAV; (None, None) otherwise."""
    try:
        with contextlib.closing(wave.open(str(path), "rb")) as w:
            rate = w.getframerate()
            duration = w.getnframes() / float(rate) if rate else None
            return duration, rate
    except (wave.Error, EOFError, OSError):
        return None, None


class AudioStore:
    """Stores audio assets and ingests recordings (normalize + dedupe)."""

    def __init__(self, db_path: str, clock: Clock | None = None) -> None:
        if db_path not in (":memory:", "") and "mode=memory" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: shared across FastAPI worker threads (see corpus/store.py).
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._clock = clock or SystemClock()

    # -- ingestion -----------------------------------------------------------
    def store_file(
        self,
        source_path: str | Path,
        *,
        owner: str,
        audio_dir: str,
        original_filename: str | None = None,
    ) -> AudioAsset:
        """Normalize + store a recording, deduped by content hash (idempotent)."""
        source = Path(source_path)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        existing = self.get_by_sha256(digest)
        if existing is not None:
            return existing  # same audio already stored — return it unchanged

        asset_id = str(uuid.uuid4())
        out_dir = Path(audio_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = original_filename or source.name
        dst = self._normalize(source, out_dir, asset_id)
        duration_s, sample_rate = _wav_meta(dst)

        asset = AudioAsset(
            id=asset_id,
            owner=owner,
            filename=filename,
            path=str(dst),
            duration_s=duration_s,
            sample_rate=sample_rate,
            sha256=digest,
            created_at=self._clock.now(),
        )
        return self.save(asset)

    def _normalize(self, source: Path, out_dir: Path, asset_id: str) -> Path:
        """ffmpeg → mono 16 kHz WAV; fall back to a verbatim copy (with a warning)."""
        if shutil.which("ffmpeg") is not None:
            dst = out_dir / f"{asset_id}.wav"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
                     "-ac", "1", "-ar", "16000", str(dst)],
                    check=True, capture_output=True,
                )
                return dst
            except (subprocess.CalledProcessError, OSError) as exc:
                warnings.warn(
                    f"ffmpeg normalization failed ({exc}); storing audio as-is.",
                    stacklevel=2,
                )
        else:
            warnings.warn(
                "ffmpeg not found; storing audio without normalization "
                "(transcription quality may suffer).",
                stacklevel=2,
            )
        dst = out_dir / f"{asset_id}{source.suffix}"
        shutil.copyfile(source, dst)
        return dst

    # -- persistence ---------------------------------------------------------
    def save(self, asset: AudioAsset) -> AudioAsset:
        self._conn.execute(
            "INSERT OR REPLACE INTO audio_assets (id, owner, filename, path, duration_s, "
            "sample_rate, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                asset.id, asset.owner, asset.filename, asset.path,
                asset.duration_s, asset.sample_rate, asset.sha256,
                asset.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return asset

    def get(self, asset_id: str) -> AudioAsset | None:
        row = self._conn.execute(
            "SELECT * FROM audio_assets WHERE id = ?", (asset_id,)
        ).fetchone()
        return self._row_to_asset(row) if row else None

    def get_by_sha256(self, sha256: str) -> AudioAsset | None:
        row = self._conn.execute(
            "SELECT * FROM audio_assets WHERE sha256 = ?", (sha256,)
        ).fetchone()
        return self._row_to_asset(row) if row else None

    def list_assets(self, limit: int = 50) -> list[AudioAsset]:
        rows = self._conn.execute(
            "SELECT * FROM audio_assets ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [self._row_to_asset(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> AudioStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row_to_asset(row: sqlite3.Row) -> AudioAsset:
        return AudioAsset(
            id=row["id"],
            owner=row["owner"],
            filename=row["filename"],
            path=row["path"],
            duration_s=row["duration_s"],
            sample_rate=row["sample_rate"],
            sha256=row["sha256"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
