"""The UI shell is split across index.html + styles.css + app.js + auth.js (A1).

These tests guard the two things that split can silently break:

1. **Serving.** Each asset must be reachable, with the right content type, or the app
   loads as unstyled HTML with no behavior — which looks like "the UI is broken" and
   not like "a route is missing".
2. **Module scope.** `app.js` is loaded as `type="module"`, so its top-level
   declarations are NOT global. Every function invoked from an inline `onclick="…"`
   — in the markup or in generated HTML — must be explicitly put on `window`. Under
   the old classic script that happened for free; now it is an invariant, and the one
   function that had been relying on the leak (`openThread`) is why this is tested.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "maayan" / "ui" / "static"

INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")
AUTH_JS = (STATIC / "auth.js").read_text(encoding="utf-8")
STYLES = (STATIC / "styles.css").read_text(encoding="utf-8")

# `on*="…"` attribute values, in the markup and inside generated HTML strings.
_HANDLER = re.compile(r"""\bon[a-z]+\s*=\s*(?:(["'])(.*?)\1|\\(["'])(.*?)\\\3)""", re.S)
# `${…}` interpolations run at string-BUILD time, in module scope — they are fine.
_INTERP = re.compile(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")
_CALL = re.compile(r"([A-Za-z_$][\w$]*)\s*\(")
_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "typeof", "function"}
# Browser globals that are legitimately callable from a handler.
_BUILTINS = {"confirm", "alert", "fetch", "Number", "String", "JSON", "parseInt", "parseFloat"}


def _click_time_calls(*sources: str) -> set[str]:
    """Identifiers invoked when a handler FIRES (interpolations excluded)."""
    names: set[str] = set()
    for src in sources:
        for match in _HANDLER.finditer(src):
            body = match.group(2) if match.group(2) is not None else (match.group(4) or "")
            names.update(_CALL.findall(_INTERP.sub("", body)))
    return names - _KEYWORDS - _BUILTINS


def _window_globals(src: str) -> set[str]:
    return set(re.findall(r"window\.(\w+)\s*=", src))


def test_shell_html_links_the_extracted_assets_as_modules() -> None:
    assert '<link rel="stylesheet" href="/styles.css">' in INDEX
    assert '<script type="module" src="/app.js"></script>' in INDEX
    assert '<script type="module" src="/auth.js"></script>' in INDEX


def test_no_inline_style_or_script_blocks_remain() -> None:
    # The whole point of the split: markup only. (`<link>`/`<script src>` are fine.)
    assert "<style>" not in INDEX
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", INDEX), "an inline <script> is back"


def test_every_inline_handler_target_is_reachable_from_module_scope() -> None:
    """The invariant that makes `type="module"` safe here."""
    exposed = _window_globals(APP_JS) | _window_globals(AUTH_JS)
    missing = sorted(_click_time_calls(INDEX, APP_JS) - exposed)
    assert not missing, (
        "these run from an inline handler but are not on `window`, so under module "
        f"scope the control silently does nothing: {missing}"
    )


def test_openthread_specifically_is_exposed() -> None:
    # The one function that had been relying on the classic-script global leak.
    assert "window.openThread = openThread;" in APP_JS


def test_extracted_files_are_non_trivial_and_free_of_wrapper_tags() -> None:
    """Guards a botched re-extraction that leaves the wrapper tags in, or empties a file.

    Note `app.js` legitimately CONTAINS `<style>` and `<html>` — it builds a print
    document as a string for the RTL export. So the check is that the wrapper the
    content was carved out of is gone, not that no markup appears anywhere.
    """
    assert len(APP_JS.splitlines()) > 1000
    assert len(AUTH_JS.splitlines()) > 50
    assert len(STYLES.splitlines()) > 100
    for name, body in (("app.js", APP_JS), ("auth.js", AUTH_JS)):
        assert "</script>" not in body, f"{name} still contains its wrapper close tag"
        assert not body.lstrip().startswith("<script"), name
    assert "<style>" not in STYLES and "</style>" not in STYLES
    # CSS starts with a rule or a comment, never markup.
    assert not STYLES.lstrip().startswith("<")


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/styles.css", "text/css"),
        ("/app.js", "text/javascript"),
        ("/auth.js", "text/javascript"),
    ],
)
def test_assets_are_served_with_the_right_content_type(path: str, content_type: str) -> None:
    from tests.test_ui import _client  # reuse the app fixture wiring

    client, _rag, _capture = _client()
    response = client.get(path)
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]
    assert response.text.strip()


def test_service_worker_keeps_the_shell_usable_offline() -> None:
    """Inline CSS/JS made a cached shell self-contained; split out, they must be cached too."""
    sw = (STATIC / "sw.js").read_text(encoding="utf-8")
    for asset in ("/styles.css", "/app.js", "/auth.js"):
        assert asset in sw, f"{asset} is not handled by the service worker"
    # Network-first, not cache-first: a stale app.js is worse than a slow one.
    assert "SHELL_ASSETS" in sw
    assert "STATIC = [" in sw
    static_list = sw.split("STATIC = [", 1)[1].split("]", 1)[0]
    assert "app.js" not in static_list, "shell JS must not be in the cache-first list"
