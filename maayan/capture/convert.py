"""Convert expert annotations into retrievable chunks.

This is what closes the loop: an expert's note becomes a `Chunk` with
`source="expert"`, indexed into the SAME Qdrant collection as the printed text, so
it surfaces in future retrieval alongside (and, with `expert_boost`, ahead of) the
sources. Author, kind, linked_refs and the move tag are preserved in metadata.
"""

from __future__ import annotations

import re

from maayan.capture.models import Annotation
from maayan.corpus.models import Chunk, Lang

EXPERT_SOURCE = "expert"
_HEBREW = re.compile(r"[֐-׿]")


def detect_lang(text: str) -> Lang:
    """Cheap he/en detector: any Hebrew letter → 'he', else 'en'."""
    return "he" if _HEBREW.search(text) else "en"


def annotation_to_chunks(annotation: Annotation) -> list[Chunk]:
    """Turn an annotation into one retrievable expert chunk.

    The embedded text is the expert's body plus the linked refs and move tag, so
    the note is retrievable both by its content and by the sources it connects.
    """
    linked = ", ".join(annotation.linked_refs)
    parts = [annotation.body]
    if linked:
        parts.append(f"[{annotation.kind} ↔ {linked}]")
    if annotation.move:
        parts.append(f"(move: {annotation.move})")
    text = " ".join(parts)

    ref = f"Expert · {annotation.kind} · {annotation.id[:8]}"
    metadata: dict[str, object] = {
        "author": annotation.author,
        "kind": annotation.kind,
        "linked_refs": annotation.linked_refs,
        "move": annotation.move,
        "session_id": annotation.session_id,
        "annotation_id": annotation.id,
    }
    return [
        Chunk.make(
            ref=ref,
            book="Expert",
            section_path=[annotation.kind, f"by {annotation.author}"],
            lang=detect_lang(annotation.body),
            text=text,
            source=EXPERT_SOURCE,
            metadata=metadata,
        )
    ]
