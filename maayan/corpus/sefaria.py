"""Async client for the Sefaria API (v3 text + shape).

DI throughout: the `httpx.AsyncClient` and the `Clock` are injected. Rate limiting
is driven by the injected clock (`await clock.sleep(...)`), never `time.sleep`, so
tests run instantly with a `FakeClock`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

import httpx

from maayan.clock import Clock
from maayan.corpus.models import SefariaSection, SefariaSegment, SefariaShape


class SefariaError(RuntimeError):
    """Raised when Sefaria returns an error payload or an unexpected shape."""


class SefariaClient:
    """Fetches text + structure from Sefaria. Stateless except for rate-limit timing."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        clock: Clock,
        *,
        base_url: str = "https://www.sefaria.org/api",
        rate_limit_seconds: float = 0.5,
    ) -> None:
        self._http = http
        self._clock = clock
        self._base_url = base_url.rstrip("/")
        self._rate_limit_seconds = rate_limit_seconds
        self._last_request: float | None = None

    # -- HTTP plumbing -------------------------------------------------------
    async def _throttle(self) -> None:
        """Ensure at least `rate_limit_seconds` between requests, via the Clock."""
        if self._last_request is not None:
            wait = self._rate_limit_seconds - (self._clock.monotonic() - self._last_request)
            if wait > 0:
                await self._clock.sleep(wait)
        self._last_request = self._clock.monotonic()

    async def _get_json(
        self, path: str, params: httpx.QueryParams | None = None
    ) -> Any:
        await self._throttle()
        resp = await self._http.get(f"{self._base_url}/{path}", params=params)
        resp.raise_for_status()
        data: Any = resp.json()
        if isinstance(data, dict) and data.get("error"):
            raise SefariaError(str(data["error"]))
        return data

    # -- Public API ----------------------------------------------------------
    async def fetch_shape(self, base_ref: str) -> SefariaShape:
        """Return the structure (paragraphs-per-chapter) for a base/node ref."""
        data = await self._get_json(f"shape/{quote(base_ref)}")
        node = data[0] if isinstance(data, list) else data
        chapters = node.get("chapters")
        if not isinstance(chapters, list) or not all(isinstance(c, int) for c in chapters):
            raise SefariaError(
                f"Unsupported shape for {base_ref!r}: expected a flat list of chapter "
                f"lengths (depth-2 text), got {type(chapters).__name__}."
            )
        return SefariaShape(
            ref=str(node.get("title") or node.get("ref") or base_ref),
            book=str(node.get("book") or base_ref),
            chapter_lengths=chapters,
        )

    async def fetch_section(self, section_ref: str) -> SefariaSection:
        """Fetch one section (e.g. a chapter) and return its ordered segments."""
        data = await self._get_json(
            f"v3/texts/{quote(section_ref)}",
            params=httpx.QueryParams([("version", "primary"), ("version", "translation")]),
        )
        return self._parse_section(data)

    async def iter_book_sections(
        self, base_ref: str, *, max_chapters: int | None = None
    ) -> AsyncIterator[SefariaSection]:
        """Yield each chapter-section of a book in order, using its shape to enumerate."""
        shape = await self.fetch_shape(base_ref)
        n = shape.num_chapters if max_chapters is None else min(max_chapters, shape.num_chapters)
        for chapter in range(1, n + 1):
            yield await self.fetch_section(f"{base_ref} {chapter}")

    # -- Parsing -------------------------------------------------------------
    @staticmethod
    def _parse_section(data: dict[str, Any]) -> SefariaSection:
        ref = str(data["ref"])
        book = str(data.get("book") or ref)
        section_names: list[str] = list(data.get("sectionNames") or ["Section", "Segment"])
        sections: list[str] = [str(s) for s in (data.get("sections") or [])]

        # Pick the first version per language; align segments by index.
        texts_by_lang: dict[str, list[str]] = {}
        for version in data.get("versions") or []:
            lang = version.get("language")
            text = version.get("text")
            if lang in ("he", "en") and isinstance(text, list) and lang not in texts_by_lang:
                texts_by_lang[lang] = [t if isinstance(t, str) else "" for t in text]

        he = texts_by_lang.get("he", [])
        en = texts_by_lang.get("en", [])
        count = max(len(he), len(en))

        # Structural prefix for refs/paths: everything above the segment level.
        chapter_label = (
            f"{section_names[0]} {sections[0]}" if section_names and sections else ref
        )
        seg_name = section_names[1] if len(section_names) > 1 else "Segment"

        segments: list[SefariaSegment] = []
        for i in range(count):
            n = i + 1
            segments.append(
                SefariaSegment(
                    ref=f"{ref}:{n}",
                    book=book,
                    section_path=[chapter_label, f"{seg_name} {n}"],
                    he=he[i] if i < len(he) else None,
                    en=en[i] if i < len(en) else None,
                )
            )
        return SefariaSection(
            ref=ref,
            book=book,
            section_names=section_names,
            segments=segments,
            metadata={"heRef": data.get("heRef")} if data.get("heRef") else {},
        )
