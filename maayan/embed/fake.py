"""A deterministic, dependency-free embedder for tests and no-GPU demos.

`HashingEmbedder` hashes tokens into dense buckets and a sparse term space. It is
NOT semantically meaningful — shared tokens just produce overlapping vectors, which
is enough to exercise the index/retrieval pipeline (and rank shared-vocab matches
above unrelated ones) without downloading bge-m3. Never use it for real retrieval
quality. It satisfies the `Embedder` protocol so it drops in via DI.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from maayan.embed.base import Embedding

_TOKEN = re.compile(r"\w+", re.UNICODE)
_SPARSE_SPACE = 100_000


def _hash_int(token: str) -> int:
    return int.from_bytes(hashlib.md5(token.encode("utf-8")).digest()[:8], "big")


class HashingEmbedder:
    """Deterministic dense+sparse embeddings from token hashes."""

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _embed_one(self, text: str) -> Embedding:
        tokens = _TOKEN.findall(text.lower())
        dense = [0.0] * self._dim
        sparse: dict[int, float] = {}
        for tok in tokens:
            h = _hash_int(tok)
            bucket = h % self._dim
            sign = 1.0 if (h >> 1) & 1 else -1.0
            dense[bucket] += sign
            idx = h % _SPARSE_SPACE
            sparse[idx] = sparse.get(idx, 0.0) + 1.0
        norm = math.sqrt(sum(v * v for v in dense)) or 1.0
        dense = [v / norm for v in dense]
        return Embedding(
            dense=dense,
            sparse_indices=list(sparse.keys()),
            sparse_values=list(sparse.values()),
        )

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> Embedding:
        return self._embed_one(text)
