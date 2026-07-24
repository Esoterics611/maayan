"""Tests for the cross-encoder reranker wiring — no model downloads, no network.

The real model is exercised by the eval harness; these pin the contract and the
construction path. The bug being guarded: `BGEReranker` used to go through
FlagEmbedding's `FlagReranker`, which calls `tokenizer.prepare_for_model` — removed
in transformers 5 — so ANY call raised AttributeError. Nothing caught it because the
reranker is off by default, so no test and no default code path ever ran it.
"""

from __future__ import annotations

import types
from collections.abc import Sequence
from typing import Any

from maayan.config import Settings
from maayan.embed.device import resolve_device
from maayan.retrieve.reranker import Reranker


class _StubReranker:
    """A `Reranker` that scores by keyword — enough to exercise callers."""

    def __init__(self, token: str) -> None:
        self._token = token

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        return [1.0 if self._token in doc else 0.0 for doc in documents]


def test_stub_satisfies_the_protocol() -> None:
    # `Reranker` is runtime_checkable, so DI seams can assert on it.
    assert isinstance(_StubReranker("x"), Reranker)


def test_resolve_device_passes_explicit_values_through_untouched() -> None:
    # No torch import happens on this path, so it is safe without the ML extras.
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("cuda:1") == "cuda:1"
    assert resolve_device("mps") == "mps"


def test_rerank_device_falls_back_to_embed_device() -> None:
    """One knob for the common case; a separate one only when the models must differ."""
    shared = Settings(embed_device="cuda", rerank_device="")
    assert (shared.rerank_device or shared.embed_device) == "cuda"

    split = Settings(embed_device="cuda", rerank_device="cpu")
    assert (split.rerank_device or split.embed_device) == "cpu"


class _FakeTokenizer:
    """Records the pairs it was asked to encode and returns a dummy batch."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], list[str]]] = []

    def __call__(self, queries: list[str], docs: list[str], **kw: Any) -> Any:
        self.calls.append((queries, docs))
        batch = types.SimpleNamespace(to=lambda device: {"n": len(docs)})
        return batch


def test_reranker_batches_pairs_and_preserves_document_order(monkeypatch: Any) -> None:
    """Scores come back aligned to the documents given, across batch boundaries."""
    from maayan.retrieve import reranker as mod

    class _Model:
        def __call__(self, *, n: int) -> Any:
            # Logits chosen so sigmoid is monotonically increasing with position.
            return types.SimpleNamespace(logits=_Tensor([float(i) for i in range(n)]))

    class _Tensor(list[float]):
        def view(self, _: int) -> _Tensor:
            return self

        def float(self) -> _Tensor:
            return self

    fake_torch = types.SimpleNamespace(
        no_grad=lambda: _NullCtx(),
        sigmoid=lambda t: [1 / (1 + pow(2.718281828, -x)) for x in t],
    )

    rr = mod.BGEReranker.__new__(mod.BGEReranker)  # bypass model loading
    rr._tokenizer = _FakeTokenizer()  # type: ignore[attr-defined]
    rr._model = _Model()  # type: ignore[attr-defined]
    rr._torch = fake_torch  # type: ignore[attr-defined]
    rr._device = "cpu"  # type: ignore[attr-defined]
    rr._max_length = 512  # type: ignore[attr-defined]
    rr._batch_size = 2  # type: ignore[attr-defined]

    scores = rr.rerank("q", ["a", "b", "c"])
    assert len(scores) == 3
    assert all(0.0 <= s <= 1.0 for s in scores)  # sigmoid-normalized
    # 3 docs at batch_size 2 → two forward passes, documents split in order.
    assert rr._tokenizer.calls == [(["q", "q"], ["a", "b"]), (["q"], ["c"])]  # type: ignore[attr-defined]


def test_reranker_short_circuits_on_no_documents() -> None:
    from maayan.retrieve import reranker as mod

    rr = mod.BGEReranker.__new__(mod.BGEReranker)
    assert rr.rerank("q", []) == []  # no tokenizer/model touched


class _NullCtx:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


def _import_lines(module: object) -> list[str]:
    """Every import statement in a module's source, docstrings and comments excluded."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))  # type: ignore[arg-type]
    lines: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            lines.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            lines.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return lines


def test_flagembedding_reranker_path_is_gone() -> None:
    """Regression guard: re-importing FlagReranker would reintroduce the crash."""
    from maayan.retrieve import reranker as mod

    imports = _import_lines(mod)
    assert not any("FlagEmbedding" in name for name in imports), (
        "FlagEmbedding's FlagReranker calls tokenizer.prepare_for_model, removed in "
        "transformers 5 — every rerank call raises AttributeError."
    )
    assert any("AutoModelForSequenceClassification" in name for name in imports)


def test_torch_and_transformers_are_imported_lazily() -> None:
    """Core installs stay light: the heavy imports live inside functions, not at module top."""
    import ast
    import inspect

    from maayan.retrieve import reranker as mod

    tree = ast.parse(inspect.getsource(mod))
    top_level = [n for n in tree.body if isinstance(n, ast.Import | ast.ImportFrom)]
    names: list[str] = []
    for node in top_level:
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif node.module:
            names.append(node.module)
    assert not any(n.startswith(("torch", "transformers")) for n in names), names
