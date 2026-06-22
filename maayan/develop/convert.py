"""Convert an APPROVED development into a retrievable derived chunk.

This closes the Phase 2 loop: an expert-seeded, model-developed, expert-approved
elaboration becomes a `source="derived"` `Chunk` in the SAME Qdrant collection as the
printed text and the expert notes. Printed text stays immutable — derived knowledge
layers on top as a separate chunk, carrying full provenance (which seed, whose seed,
which model developed it, the refs it was grounded on, the thread).
"""

from __future__ import annotations

from maayan.capture.convert import detect_lang
from maayan.corpus.models import Chunk
from maayan.develop.models import Development

DERIVED_SOURCE = "derived"
DERIVED_BOOK = "Derived"


def development_to_chunk(dev: Development, *, book: str = DERIVED_BOOK) -> Chunk:
    """Turn an approved Development into one derived corpus chunk with provenance."""
    ref = f"Derived · {dev.id[:8]}"
    metadata: dict[str, object] = {
        "seed_id": dev.seed_id,
        "author": dev.author,
        "developed_by": dev.model,
        "grounded_in": dev.grounded_in,
        "thread_id": dev.thread_id,
        "development_id": dev.id,
    }
    return Chunk.make(
        ref=ref,
        book=book,
        section_path=[book, f"from seed {dev.seed_id[:8]}"],
        lang=detect_lang(dev.text),
        text=dev.text,
        source=DERIVED_SOURCE,
        metadata=metadata,
    )
