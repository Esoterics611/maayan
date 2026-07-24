"""Optional cross-encoder reranker (BAAI/bge-reranker-v2-m3).

Injectable behind the `Reranker` protocol so it can be disabled (None) in tests and
swapped. torch/transformers are imported lazily.

Implemented directly on `transformers` rather than through FlagEmbedding's
`FlagReranker`: that path calls `tokenizer.prepare_for_model`, which transformers 5
removed, so it raises `AttributeError` on every call in this environment. The
embedder is unaffected (different code path), which is why the breakage stayed
invisible — the reranker is off by default, so nothing exercised it.

A cross-encoder scores (query, document) jointly instead of comparing two independent
embeddings, which is why its score is a better relevance signal than bi-encoder
cosine — and why it is worth carrying to the gate. Scores are sigmoid-normalized to
0..1 so a threshold against them is interpretable.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from maayan.config import Settings


@runtime_checkable
class Reranker(Protocol):
    """Scores (query, document) pairs; higher = more relevant."""

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        ...


class BGEReranker:
    """bge-reranker-v2-m3 as a plain transformers sequence-classification model."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        *,
        device: str = "auto",
        use_fp16: bool = True,
        max_length: int = 512,
        batch_size: int = 16,
    ) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        from maayan.embed.device import resolve_device

        resolved = resolve_device(device)
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        # fp16 only helps (and only behaves) on CUDA.
        if use_fp16 and resolved.startswith("cuda"):
            model = model.half()
        self._model = model.to(resolved).eval()
        self._torch = torch
        self._device = resolved
        self._max_length = max_length
        self._batch_size = batch_size

    @property
    def device(self) -> str:
        return self._device

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        """Relevance in 0..1 for each document, in the order given."""
        docs = list(documents)
        if not docs:
            return []
        scores: list[float] = []
        for start in range(0, len(docs), self._batch_size):
            batch = docs[start : start + self._batch_size]
            scores.extend(self._score_batch(query, batch))
        return scores

    def _score_batch(self, query: str, batch: Sequence[str]) -> list[float]:
        inputs: Any = self._tokenizer(
            [query] * len(batch),
            list(batch),
            padding=True,
            truncation=True,
            max_length=self._max_length,
            return_tensors="pt",
        ).to(self._device)
        with self._torch.no_grad():
            logits = self._model(**inputs).logits.view(-1).float()
            return [float(x) for x in self._torch.sigmoid(logits)]


def build_reranker(settings: Settings) -> Reranker:
    """Construct the configured reranker (DI at the edge)."""
    return BGEReranker(
        settings.rerank_model,
        device=settings.rerank_device or settings.embed_device,
        max_length=settings.rerank_max_length,
        batch_size=settings.rerank_batch_size,
    )
