"""Concrete `Embedder` backed by BAAI/bge-m3 via FlagEmbedding.

One model pass yields both the dense vector and the sparse (lexical) weights, which
is exactly what hybrid search needs. The model is loaded once in the constructor
(heavy) and reused. FlagEmbedding/torch are imported lazily so the rest of the
package — and the unit tests — don't require the ML extras to be installed.
"""

from __future__ import annotations

from collections.abc import Sequence

from maayan.embed.base import Embedding


def _resolve_device(device: str) -> str:
    """Map "auto" to the best available torch device."""
    if device != "auto":
        return device
    import torch

    if torch.cuda.is_available():
        return "cuda:0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class BGEM3Embedder:
    """Local bge-m3 embedder producing dense (1024-d) + sparse vectors."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        *,
        device: str = "auto",
        batch_size: int = 16,
        dim: int = 1024,
        use_fp16: bool = True,
        max_length: int = 8192,
    ) -> None:
        from FlagEmbedding import BGEM3FlagModel

        resolved = _resolve_device(device)
        # fp16 only helps (and only works well) on CUDA.
        fp16 = use_fp16 and resolved.startswith("cuda")
        self._model = BGEM3FlagModel(model_name, use_fp16=fp16, devices=resolved)
        self._dim = dim
        self._batch_size = batch_size
        self._max_length = max_length
        self.device = resolved

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        items = list(texts)
        if not items:
            return []
        out = self._model.encode(
            items,
            batch_size=self._batch_size,
            max_length=self._max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = out["dense_vecs"]
        lexical = out["lexical_weights"]
        results: list[Embedding] = []
        for i in range(len(items)):
            weights = lexical[i]
            results.append(
                Embedding(
                    dense=[float(x) for x in dense[i]],
                    sparse_indices=[int(k) for k in weights.keys()],
                    sparse_values=[float(v) for v in weights.values()],
                )
            )
        return results

    def embed_query(self, text: str) -> Embedding:
        return self.embed([text])[0]
