"""Every surface must expand queries the same way (R3).

`query_expand_enabled` is one flag, but expansion is only as strong as what the
factory hands `build_retriever`: without a `backend` the composite expander degrades
to lexicon-only — no LLM reformulations, no HyDE. `ask` passed a backend and every
other surface did not, so the same flag quietly meant two different things depending
on where you were standing. These tests pin the parity down.

No network: the backend is a stub and the embedder is the hashing one.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence

import pytest

from maayan.config import Settings
from maayan.embed.fake import HashingEmbedder
from maayan.generate.base import Message
from maayan.retrieve.factory import build_retriever
from maayan.retrieve.retriever import MultiQueryRetriever, Retriever


class _StubBackend:
    """A GenerationBackend that returns fixed reformulations without any network."""

    def generate(self, system: str, messages: Sequence[Message]) -> str:
        return "וריאציה ראשונה\nוריאציה שנייה"


@pytest.fixture
def settings(tmp_path: object) -> Settings:
    return Settings(
        qdrant_url=":memory:",
        db_path=f"{tmp_path}/t.sqlite3",  # type: ignore[str-bytes-safe]
        embed_backend="hashing",
        embed_dim=64,
        query_expand_enabled=True,
        query_expand_lexicon=True,
    )


def test_backend_is_what_upgrades_expansion_beyond_the_lexicon(settings: Settings) -> None:
    emb = HashingEmbedder(dim=64)
    without = build_retriever(settings, embedder=emb, backend=None)
    with_backend = build_retriever(settings, embedder=emb, backend=_StubBackend())

    # Both are multi-query (the lexicon expander alone already wraps)...
    assert isinstance(without, MultiQueryRetriever)
    assert isinstance(with_backend, MultiQueryRetriever)
    # ...but only the second one can produce LLM reformulations / HyDE.
    assert _expander_count(with_backend) > _expander_count(without)


def test_expansion_off_yields_the_plain_retriever(settings: Settings) -> None:
    plain = build_retriever(
        settings.model_copy(update={"query_expand_enabled": False}),
        embedder=HashingEmbedder(dim=64),
        backend=_StubBackend(),
    )
    assert isinstance(plain, Retriever)


@pytest.mark.parametrize(
    "factory_path",
    [
        "maayan.compose.factory.build_composition_service",
        "maayan.develop.factory.build_development_service",
        "maayan.develop.factory.build_develop_eval_setup",
        "maayan.lexicon.factory.build_lexicon_populator",
        "maayan.agent.program_factory.build_study_program_runner",
    ],
)
def test_every_surface_hands_its_backend_to_build_retriever(factory_path: str) -> None:
    """Each service factory already builds a backend — it must also pass it on.

    Asserted on the source rather than by constructing the services, because building
    them for real needs an API key and a live Qdrant. The failure this guards against
    is a `build_retriever(...)` call that silently omits `backend=`.
    """
    module_name, func_name = factory_path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[func_name])
    source = inspect.getsource(getattr(module, func_name))
    assert "build_retriever(" in source, f"{factory_path} no longer builds a retriever"
    for call in _build_retriever_calls(source):
        assert "backend=" in call, (
            f"{factory_path} calls build_retriever without backend= — query expansion "
            f"there degrades to lexicon-only while `ask` gets LLM reformulations:\n{call}"
        )


def _build_retriever_calls(source: str) -> list[str]:
    """Every `build_retriever(...)` call in `source`, balanced across line breaks."""
    calls: list[str] = []
    marker = "build_retriever("
    start = source.find(marker)
    while start != -1:
        depth = 0
        for i in range(start + len(marker) - 1, len(source)):
            if source[i] == "(":
                depth += 1
            elif source[i] == ")":
                depth -= 1
                if depth == 0:
                    calls.append(source[start : i + 1])
                    break
        start = source.find(marker, start + 1)
    return calls


def _expander_count(retriever: MultiQueryRetriever) -> int:
    composite = retriever._expander  # noqa: SLF001 — asserting on wiring is the point
    return len(composite._expanders)  # noqa: SLF001
