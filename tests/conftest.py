"""Shared test fixtures. No network, no real models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def shape_json() -> Any:
    return load_fixture("sefaria_shape_likkutei_amarim.json")


@pytest.fixture
def chapter1_json() -> Any:
    return load_fixture("sefaria_likkutei_amarim_ch1.json")


@pytest.fixture
def chapter2_json() -> Any:
    return load_fixture("sefaria_likkutei_amarim_ch2.json")


@pytest.fixture
def links_tanya_18_1_json() -> Any:
    """Real /api/links payload for Tanya 18:1 (one Tanakh link), trimmed."""
    return load_fixture("sefaria_links_tanya_18_1.json")


@pytest.fixture
def links_tanya_1_1_json() -> Any:
    """Real /api/links payload for Tanya 1:1 (mixed categories), trimmed."""
    return load_fixture("sefaria_links_tanya_1_1.json")
