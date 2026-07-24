"""Shared test fixtures. No network, no real models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# The UI shell used to be a single index.html with inline <style>/<script>. A1 split
# it into index.html + styles.css + app.js + auth.js. A test asserting that some
# affordance SHIPS should look at the whole shell — which of those files a given
# marker landed in is an implementation detail of the split, not behavior.
UI_SHELL_PATHS = ("/", "/app.js", "/auth.js", "/styles.css")


def ui_shell(client: Any) -> str:
    """Concatenate every part of the served UI shell into one searchable string."""
    return "\n".join(client.get(path).text for path in UI_SHELL_PATHS)


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
