"""Convert an approved transcript into retrievable `source="shiur"` chunks.

This closes the voice loop: a reviewed shiur becomes corpus in the SAME collection as
the printed text, retrievable alongside it. Consecutive segments are packed up to a
character budget (chabad_chunk_chars-style) so a chunk is a coherent passage, not a
single utterance; each chunk keeps its audio_id + start/end timestamps so a citation
can play from the moment. Printed text stays immutable — this only layers on top.
"""

from __future__ import annotations

from maayan.capture.convert import detect_lang
from maayan.corpus.models import Chunk
from maayan.transcribe.models import Transcript, TranscriptSegment

SHIUR_SOURCE = "shiur"
SHIUR_BOOK = "Shiur"


def _fmt_ts(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def _window(
    segments: list[TranscriptSegment], *, max_chars: int
) -> list[tuple[float, float, str | None, str]]:
    """Pack consecutive segments into (start_s, end_s, speaker, text) windows.

    Greedy to `max_chars` (0 → one window for the whole transcript). Empty segments
    are skipped; a window's speaker is the first segment's speaker.
    """
    windows: list[tuple[float, float, str | None, str]] = []
    parts: list[str] = []
    start = end = 0.0
    speaker: str | None = None
    for seg in segments:
        text = seg.display_text.strip()
        if not text:
            continue
        if parts and max_chars > 0 and len(" ".join(parts)) + 1 + len(text) > max_chars:
            windows.append((start, end, speaker, " ".join(parts)))
            parts, start, end, speaker = [text], seg.start_s, seg.end_s, seg.speaker
        else:
            if not parts:
                start, speaker = seg.start_s, seg.speaker
            parts.append(text)
            end = seg.end_s
    if parts:
        windows.append((start, end, speaker, " ".join(parts)))
    return windows


def transcript_to_chunks(
    transcript: Transcript, *, title: str, author: str, max_chars: int = 0
) -> list[Chunk]:
    """Window an approved transcript into shiur chunks with provenance + timestamps."""
    chunks: list[Chunk] = []
    for i, (start_s, end_s, speaker, text) in enumerate(
        _window(transcript.segments, max_chars=max_chars), start=1
    ):
        ref = f"Shiur: {title} §{i} @ {_fmt_ts(start_s)}"
        metadata: dict[str, object] = {
            "audio_id": transcript.audio_id,
            "transcript_id": transcript.id,
            "start_s": start_s,
            "end_s": end_s,
            "speaker": speaker,
            "author": author,
            "title": title,
        }
        chunks.append(
            Chunk.make(
                ref=ref,
                book=title,  # each shiur is its own "book" → Library browses shiurim by title
                section_path=[SHIUR_BOOK],
                lang=detect_lang(text),
                text=text,
                source=SHIUR_SOURCE,
                metadata=metadata,
            )
        )
    return chunks
