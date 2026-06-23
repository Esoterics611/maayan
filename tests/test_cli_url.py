"""The startup-banner URL helper: 0.0.0.0 is a bind address, not a browsable URL."""

from __future__ import annotations

from maayan.cli import _ui_display_urls


def test_specific_host_passthrough() -> None:
    assert _ui_display_urls("127.0.0.1", 8000) == ["http://127.0.0.1:8000"]
    assert _ui_display_urls("example.com", 9000) == ["http://example.com:9000"]


def test_wildcard_lists_loopback_first() -> None:
    urls = _ui_display_urls("0.0.0.0", 8000)
    # Always offers a routable loopback URL (never the unbrowsable 0.0.0.0).
    assert urls[0] == "http://127.0.0.1:8000"
    assert all("0.0.0.0" not in u for u in urls)
    # If a primary IP is found, it's offered too (e.g. the WSL2 / LAN address).
    assert all(u.startswith("http://") and u.endswith(":8000") for u in urls)
