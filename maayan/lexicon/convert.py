"""Convert a Term into a retrievable `source="term"` lexicon chunk.

The embedded text is the knowledge (canonical + definition) only; the matching
machinery (surface_forms) and provenance ride in metadata, so retrieval is by the
term's *meaning*, while surface_forms drive lookup + the protected-terms deny-list.
"""

from __future__ import annotations

from maayan.capture.convert import detect_lang
from maayan.corpus.models import Chunk
from maayan.lexicon.models import Term

TERM_SOURCE = "term"
TERM_BOOK = "Lexicon"


def term_to_chunk(term: Term, *, book: str = TERM_BOOK) -> Chunk:
    """Turn a Term into one lexicon chunk with full provenance in metadata."""
    text = f"{term.canonical} — {term.definition}"
    ref = f"Term · {term.canonical}"
    metadata: dict[str, object] = {
        "surface_forms": term.surface_forms,
        "term_type": term.term_type,
        "related_terms": term.related_terms,
        "source_refs": term.source_refs,
        "gematria": term.gematria,
        "sacred": term.sacred,
        "author": term.author,
        "term_id": term.id,
    }
    return Chunk.make(
        ref=ref,
        book=book,
        section_path=[book, term.term_type],
        lang=detect_lang(text),
        text=text,
        source=TERM_SOURCE,
        metadata=metadata,
    )
