#!/usr/bin/env python3
"""Remove fully-blank pages from a PDF (no text AND no images). In place by default.

A page is kept if it has even a single character of text or any image; only truly
empty pages are dropped. Uses poppler (pdftotext/pdfimages/pdfseparate/pdfunite),
with a qpdf fast path when available.

    python3 strip_blank_pages.py input.pdf [output.pdf]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def page_count(pdf: str) -> int:
    for line in _run(["pdfinfo", pdf]).splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    raise RuntimeError("could not read page count")


def page_is_blank(pdf: str, p: int) -> bool:
    text = _run(["pdftotext", "-f", str(p), "-l", str(p), pdf, "-"]).strip()
    if text:
        return False
    # pdfimages -list prints a header row even with no images; >1 line means images.
    imgs = _run(["pdfimages", "-list", "-f", str(p), "-l", str(p), pdf]).splitlines()
    return len([ln for ln in imgs if ln.strip()]) <= 1


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: strip_blank_pages.py input.pdf [output.pdf]")
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else src

    total = page_count(src)
    keep = [p for p in range(1, total + 1) if not page_is_blank(src, p)]
    dropped = total - len(keep)
    if dropped == 0:
        if out != src:
            shutil.copyfile(src, out)
        print(f"No blank pages ({total} pages).")
        return

    with tempfile.TemporaryDirectory() as td:
        tmp_out = str(Path(td) / "out.pdf")
        if shutil.which("qpdf"):
            ranges = ",".join(str(p) for p in keep)
            _run(["qpdf", src, "--pages", src, ranges, "--", tmp_out])
        else:
            parts: list[str] = []
            for p in keep:
                part = str(Path(td) / f"p{p}.pdf")
                _run(["pdfseparate", "-f", str(p), "-l", str(p), src, part])
                parts.append(part)
            _run(["pdfunite", *parts, tmp_out])
        shutil.move(tmp_out, out)

    print(f"Stripped {dropped} blank page(s): {total} -> {len(keep)}  ->  {out}")


if __name__ == "__main__":
    main()
