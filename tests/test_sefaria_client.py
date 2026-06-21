"""Tests for SefariaClient — network mocked with respx, time mocked with FakeClock."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from maayan.clock import FakeClock
from maayan.corpus.sefaria import SefariaClient, SefariaError

BASE = "https://www.sefaria.org/api"


def _client(http: httpx.AsyncClient, clock: FakeClock) -> SefariaClient:
    return SefariaClient(http, clock, base_url=BASE, rate_limit_seconds=0.5)


@respx.mock
async def test_fetch_shape_parses_chapter_lengths(shape_json: Any) -> None:
    respx.get(url__regex=r".*/shape/.*").mock(return_value=httpx.Response(200, json=shape_json))
    async with httpx.AsyncClient() as http:
        shape = await _client(http, FakeClock()).fetch_shape("Tanya, Part I; Likkutei Amarim")
    assert shape.num_chapters == 53
    assert shape.chapter_lengths[0] == 18
    assert shape.book == "Tanya"


@respx.mock
async def test_fetch_section_parses_bilingual_segments(chapter1_json: Any) -> None:
    respx.get(url__regex=r".*/v3/texts/.*").mock(
        return_value=httpx.Response(200, json=chapter1_json)
    )
    async with httpx.AsyncClient() as http:
        section = await _client(http, FakeClock()).fetch_section(
            "Tanya, Part I; Likkutei Amarim 1"
        )
    assert section.ref == "Tanya, Part I; Likkutei Amarim 1"
    assert section.section_names == ["Chapter", "Paragraph"]
    assert len(section.segments) == 18
    first = section.segments[0]
    assert first.ref == "Tanya, Part I; Likkutei Amarim 1:1"
    assert first.section_path == ["Chapter 1", "Paragraph 1"]
    assert first.he and first.en  # both languages present in the fixture


@respx.mock
async def test_rate_limit_uses_injected_clock_not_real_sleep(
    shape_json: Any, chapter1_json: Any
) -> None:
    respx.get(url__regex=r".*/shape/.*").mock(return_value=httpx.Response(200, json=shape_json))
    respx.get(url__regex=r".*/v3/texts/.*").mock(
        return_value=httpx.Response(200, json=chapter1_json)
    )
    clock = FakeClock()
    async with httpx.AsyncClient() as http:
        client = _client(http, clock)
        sections = [s async for s in client.iter_book_sections(
            "Tanya, Part I; Likkutei Amarim", max_chapters=1
        )]
    assert len(sections) == 1
    # shape request (no wait) + 1 chapter request (one throttle wait of 0.5s),
    # recorded on the FakeClock — proving no real sleep happened.
    assert clock.slept == [0.5]


@respx.mock
async def test_error_payload_raises() -> None:
    respx.get(url__regex=r".*/v3/texts/.*").mock(
        return_value=httpx.Response(200, json={"error": "You passed 'Tanya'"})
    )
    async with httpx.AsyncClient() as http:
        with pytest.raises(SefariaError):
            await _client(http, FakeClock()).fetch_section("Tanya")
