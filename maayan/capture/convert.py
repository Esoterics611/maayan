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
    """Turn a contribution into one retrievable expert chunk.

    For a *correction/connection*, the embedded text is the expert's body plus the
    linked refs and move tag, so the note is retrievable both by its content and by
    the sources it connects.

    For a *seed* (``opens_aspect``), the embedded text is the knowledge (``body``)
    ONLY: the directive ("now develop X") is a model instruction, not knowledge, so
    it is stored in metadata and kept out of the retrievable text to avoid polluting
    retrieval. All provenance still travels in metadata.
    """
    if annotation.opens_aspect:
        text = annotation.body
    else:
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
        "opens_aspect": annotation.opens_aspect,
        "directive": annotation.directive,
        "linked_refs": annotation.linked_refs,
        "move": annotation.move,
        "session_id": annotation.session_id,
        "contribution_id": annotation.id,
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
