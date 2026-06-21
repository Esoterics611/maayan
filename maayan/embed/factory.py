"""Embedder factory — selects the concrete embedder from config (DI at the edge)."""

from __future__ import annotations

from maayan.config import Settings
from maayan.embed.base import Embedder


def build_embedder(settings: Settings) -> Embedder:
    """Construct the configured embedder. `bgem3` is real; `hashing` is dev/test."""
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
