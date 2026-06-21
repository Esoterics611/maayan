"""Embedding interfaces and data models.

`bge-m3` produces both a dense vector and a sparse (lexical) vector from one pass.
We carry both so the index supports hybrid (dense + sparse) search. The concrete
model is injected behind the `Embedder` protocol so tests and the eval harness can
swap it (e.g. for multilingual-e5 or a DICTA model) without touching callers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class Embedding(BaseModel):
    """One text's dense + sparse representation.

    Sparse is stored as parallel index/value lists, matching Qdrant's SparseVector.
    """

    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


@runtime_checkable
class Embedder(Protocol):
    """Produces dense + sparse embeddings. Loaded once, injected everywhere."""

    @property
    def dim(self) -> int:
        """Dimensionality of the dense vector."""
        ...

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        """Embed a batch of documents/texts."""
        ...

    def embed_query(self, text: str) -> Embedding:
        """Embed a single query. Symmetric models can defer to `embed`."""
        ...
