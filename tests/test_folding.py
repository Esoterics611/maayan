"""Tests for nikkud folding at the embedding boundary (R5).

The failure this prevents: Tanya is stored fully vocalized and every other book is
plain, so the vocalized text and the (always unvocalized) queries tokenized into
different lexical spaces and the sparse branch could not match Tanya at all.
"""

from __future__ import annotations

from collections.abc import Sequence

from maayan.config import Settings
from maayan.corpus.normalize import fold_for_embedding, normalize_text
from maayan.embed.base import Embedding
from maayan.embed.factory import build_embedder
from maayan.embed.fake import HashingEmbedder
from maayan.embed.folding import FoldingEmbedder

VOCALIZED = "תַּנְיָא בְּסוֹף פֶּרֶק ג׳ דְּנִדָּה"
PLAIN = "תניא בסוף פרק ג׳ דנדה"


def test_fold_removes_nikkud_and_keeps_gershayim() -> None:
    assert fold_for_embedding(VOCALIZED) == PLAIN
    # Gershayim/geresh mark rashei-teivot; removing them MERGES distinct forms
    # (ע״ב → עב) instead of aligning them, so the fold must leave them alone.
    assert fold_for_embedding("ע״ב") == "ע״ב"
    assert fold_for_embedding("וכו׳") == "וכו׳"
    assert fold_for_embedding("  double   spaced ") == "double spaced"
    assert fold_for_embedding(PLAIN) == PLAIN  # idempotent on already-plain text


def test_folding_makes_vocalized_and_plain_text_embed_identically() -> None:
    """The whole point: the same words match whether or not they carry nikkud."""
    folding = FoldingEmbedder(HashingEmbedder(dim=64), fold_for_embedding)
    vocalized, plain = folding.embed([VOCALIZED, PLAIN])
    assert vocalized.sparse_indices == plain.sparse_indices
    assert vocalized.dense == plain.dense

    # Without the fold they are different vectors — that was the bug.
    raw_v, raw_p = HashingEmbedder(dim=64).embed([VOCALIZED, PLAIN])
    assert raw_v.sparse_indices != raw_p.sparse_indices


def test_document_and_query_paths_are_folded_alike() -> None:
    """Index-time and query-time normalization cannot drift: one function, both sides."""
    folding = FoldingEmbedder(HashingEmbedder(dim=64), fold_for_embedding)
    document = folding.embed([VOCALIZED])[0]
    query = folding.embed_query(PLAIN)
    assert document.sparse_indices == query.sparse_indices


def test_folding_embedder_delegates_dim_and_exposes_inner() -> None:
    inner = HashingEmbedder(dim=64)
    folding = FoldingEmbedder(inner, fold_for_embedding)
    assert folding.dim == inner.dim == 64
    assert folding.inner is inner


class _RecordingEmbedder:
    """Captures exactly what text reached the model."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    @property
    def dim(self) -> int:
        return 2

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        self.seen.extend(texts)
        return [Embedding(dense=[0.0, 0.0], sparse_indices=[], sparse_values=[]) for _ in texts]

    def embed_query(self, text: str) -> Embedding:
        return self.embed([text])[0]


def test_stored_text_keeps_nikkud_only_the_model_input_is_folded() -> None:
    # The corpus normalizer still preserves nikkud (CLAUDE.md) ...
    stored = normalize_text(f"<b>{VOCALIZED}</b>")
    assert stored == VOCALIZED
    # ... and only what the embedder sees is folded.
    recorder = _RecordingEmbedder()
    FoldingEmbedder(recorder, fold_for_embedding).embed([stored])
    assert recorder.seen == [PLAIN]


def test_factory_wraps_when_enabled_and_not_when_disabled() -> None:
    base = Settings(embed_backend="hashing", embed_dim=32)
    assert isinstance(build_embedder(base.model_copy(update={"embed_fold_nikkud": True})),
                      FoldingEmbedder)
    plain = build_embedder(base.model_copy(update={"embed_fold_nikkud": False}))
    assert isinstance(plain, HashingEmbedder)
