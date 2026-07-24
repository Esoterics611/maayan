"""`FoldingEmbedder` — normalize text on its way into any embedder.

Index-time and query-time normalization must agree, or the lexical (sparse) branch
compares vectors built over different token spaces. Enforcing that in the ingester
would be wrong twice over: the corpus keeps nikkud on purpose (CLAUDE.md), and an
ingest-side fold could still drift from whatever the query path happens to do.

So the fold lives at the *embedding boundary* instead, as a decorator over the
`Embedder` protocol. Both `embed` (documents) and `embed_query` (queries) route
through the same function, which makes the two sides aligned by construction rather
than by convention. Stored chunk text is untouched — only what the model sees is
folded, so citations and display keep their nikkud.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from maayan.embed.base import Embedder, Embedding


class FoldingEmbedder:
    """Wraps an `Embedder`, applying `fold` to every text before it is embedded.

    Satisfies `Embedder` itself, so it drops in wherever one is injected and composes
    with any backend (bge-m3, hashing, a future model).
    """

    def __init__(self, inner: Embedder, fold: Callable[[str], str]) -> None:
        self._inner = inner
        self._fold = fold

    @property
    def dim(self) -> int:
        return self._inner.dim

    @property
    def inner(self) -> Embedder:
        """The wrapped embedder (for callers that need the concrete backend)."""
        return self._inner

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        return self._inner.embed([self._fold(t) for t in texts])

    def embed_query(self, text: str) -> Embedding:
        return self._inner.embed_query(self._fold(text))
