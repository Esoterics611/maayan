"""Torch device resolution, shared by the embedder and the reranker.

One definition so "auto" cannot mean different things to the two models loaded in the
same process — on a small card that difference is the gap between fitting and OOM.
torch is imported lazily so the core package stays installable without the ML extras.
"""

from __future__ import annotations


def resolve_device(device: str) -> str:
    """Map "auto" to the best available torch device; pass anything else through."""
    if device != "auto":
        return device
    import torch

    if torch.cuda.is_available():
        return "cuda:0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
