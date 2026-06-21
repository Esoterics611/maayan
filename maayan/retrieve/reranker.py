"""Optional cross-encoder reranker (BAAI/bge-reranker-v2-m3).

Injectable behind the `Reranker` protocol so it can be disabled (None) in tests
and swapped. FlagEmbedding/torch are imported lazily.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    """Scores (query, document) pairs; higher = more relevant."""

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        ...


class BGEReranker:
    """bge-reranker-v2-m3 via FlagEmbedding's FlagReranker."""

    def __init__(
        self, model_name: str = "BAAI/bge-reranker-v2-m3", *, use_fp16: bool = True
    ) -> None:
        from FlagEmbedding import FlagReranker

        self._model = FlagReranker(model_name, use_fp16=use_fp16)

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        if not documents:
            return []
        pairs = [[query, doc] for doc in documents]
        scores = self._model.compute_score(pairs, normalize=True)
        # FlagReranker returns a float for a single pair, else a list.
        if isinstance(scores, (int, float)):
            return [float(scores)]
        return [float(s) for s in scores]
