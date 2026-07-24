"""Embedder factory — selects the concrete embedder from config (DI at the edge)."""

from __future__ import annotations

from maayan.config import Settings
from maayan.embed.base import Embedder


def build_embedder(settings: Settings) -> Embedder:
    """Construct the configured embedder. `bgem3` is real; `hashing` is dev/test.

    When `embed_fold_nikkud` is on, the result is wrapped in a `FoldingEmbedder` so
    documents and queries are normalized identically on their way into the model —
    see `fold_for_embedding`. Wrapping here (not in the ingester) keeps the stored
    corpus vocalized while what the model sees stays aligned on both sides.
    """
    embedder = _build_base(settings)
    if settings.embed_fold_nikkud:
        from maayan.corpus.normalize import fold_for_embedding
        from maayan.embed.folding import FoldingEmbedder

        return FoldingEmbedder(embedder, fold_for_embedding)
    return embedder


def _build_base(settings: Settings) -> Embedder:
    if settings.embed_backend == "hashing":
        from maayan.embed.fake import HashingEmbedder

        return HashingEmbedder(dim=settings.embed_dim)
    if settings.embed_backend == "bgem3":
        from maayan.embed.bgem3 import BGEM3Embedder

        return BGEM3Embedder(
            settings.embed_model,
            device=settings.embed_device,
            batch_size=settings.embed_batch_size,
            dim=settings.embed_dim,
        )
    raise ValueError(f"Unknown embed_backend: {settings.embed_backend!r}")
