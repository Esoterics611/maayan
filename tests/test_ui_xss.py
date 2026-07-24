"""XSS guard for the UI's string-built markup (A3).

The UI composes HTML with template literals and assigns it to `innerHTML`. Every
`${…}` is therefore an injection site, and safety rested on remembering `esc()` at
~120 call sites — one miss on user- or model-authored text is stored XSS, and this
now runs on a public tunnel.

Rather than trusting a one-time read, this encodes the rule as a test: **any
interpolation of fetched data (a property access like `${x.y}`) must go through
`esc()` or `attr()`.** Bare identifiers (`${srcs}`) are fragments built elsewhere in
the same file and are covered transitively — their own construction is checked by the
same rule.

The audit that motivated this found 8 unescaped sites: `/kinds` values, thread and
record ids (one inside a JS string inside an HTML attribute), `status`, `turn_type`
and `source` in class attributes. All were server-controlled enums or UUIDs, so none
was exploitable — but that is a property of today's server, not of the rendering
code, and the UI models type all of them as plain `str`.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "maayan" / "ui" / "static"
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")
AUTH_JS = (STATIC / "auth.js").read_text(encoding="utf-8")


def _strip_comments(source: str) -> str:
    """Blank out comments, keeping line numbers intact (so reports stay accurate)."""
    out = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), source, flags=re.S)
    return re.sub(r"(?m)^(\s*)//.*$", lambda m: m.group(1), out)


_MARKUP = re.compile(r"<\s*[A-Za-z/!]")


def _markup_templates(source: str) -> list[tuple[int, str]]:
    """Backtick templates that actually build markup, with their start line.

    Templates without a tag — toast text, URLs, request bodies — never reach
    `innerHTML`, so an interpolation there is not an injection site.
    """
    templates: list[tuple[int, str]] = []
    i = 0
    while i < len(source):
        if source[i] != "`":
            i += 1
            continue
        k, depth = i + 1, 0
        while k < len(source):
            c = source[k]
            if c == "\\":
                k += 2
                continue
            if c == "$" and source[k + 1 : k + 2] == "{":
                depth += 1
                k += 2
                continue
            if depth and c == "{":
                depth += 1          # an object literal INSIDE an interpolation
            elif depth and c == "}":
                depth -= 1
            elif c == "`" and not depth:
                break
            k += 1
        body = source[i + 1 : k]
        if _MARKUP.search(body):
            templates.append((source.count("\n", 0, i) + 1, body))
        i = k + 1
    return templates


def _interpolations(source: str) -> list[tuple[int, str]]:
    """Every `${…}` inside a markup template, with its 1-based line number."""
    found: list[tuple[int, str]] = []
    for start_line, body in _markup_templates(_strip_comments(source)):
        i = 0
        while True:
            start = body.find("${", i)
            if start < 0:
                break
            depth, k = 0, start + 1
            while k < len(body):
                if body[k] == "{":
                    depth += 1
                elif body[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            found.append(
                (start_line + body.count("\n", 0, start), body[start + 2 : k])
            )
            i = k + 1
    return found


# Interpolations that cannot carry markup.
_SAFE = (
    re.compile(r"^\s*(esc|attr)\s*\("),           # explicitly escaped
    re.compile(r"^\s*raw\s*\("),                  # explicitly trusted, greppable on purpose
    re.compile(r"\.length\s*$"),                  # a count
    re.compile(r"\.toFixed\s*\([0-9]*\)\s*$"),    # a formatted number
    re.compile(r"^\s*fmt[A-Z]\w*\s*\("),          # fmtTs / fmtPct — numeric formatters
    re.compile(r"^[^?]*\?[^:]*:[^?:]*$"),         # ternary: both branches are literals below
)


def _is_safe(expr: str) -> bool:
    stripped = expr.strip()
    for pattern in _SAFE[:-1]:
        if pattern.search(stripped):
            return True
    # A ternary is safe when neither branch interpolates raw data of its own.
    if "?" in stripped and ":" in stripped:
        return not _raw_property_access(stripped.split("?", 1)[1])
    return False


_GLOBALS = ("Object", "JSON", "Math", "String", "Number", "Array", "document", "window")


def _raw_property_access(expr: str) -> bool:
    """True if `expr` interpolates fetched data straight into the output.

    Data that is merely an *argument* (`fmtTs(seg.start_s)`), a *lookup key*
    (`GLYPH[row.evidence]`), or inside a nested template that escapes its own
    interpolations is not an injection site — only a value that lands in the string
    verbatim is. So arguments, bracket contents and nested templates are removed
    before looking for what remains.
    """
    stripped = expr
    for pattern in (r"`[^`]*`", r"\([^()]*\)", r"\[[^\[\]]*\]"):
        previous = None
        while previous != stripped:  # repeat: nesting
            previous = stripped
            stripped = re.sub(pattern, "", stripped)
    for name in _GLOBALS:
        stripped = stripped.replace(name + ".", "")
    return bool(re.search(r"\b[A-Za-z_$][\w$]*\s*\.\s*[A-Za-z_$][\w$]*", stripped))


def _violations(source: str) -> list[tuple[int, str]]:
    bad: list[tuple[int, str]] = []
    for line, expr in _interpolations(source):
        if _is_safe(expr):
            continue
        if _raw_property_access(expr):
            bad.append((line, " ".join(expr.split())[:110]))
    return bad


def test_no_fetched_data_reaches_markup_unescaped() -> None:
    bad = _violations(APP_JS) + _violations(AUTH_JS)
    assert not bad, "unescaped data interpolated into markup:\n" + "\n".join(
        f"  app.js:{line}  ${{{expr}}}" for line, expr in bad
    )


def test_the_guard_actually_catches_a_missing_escape() -> None:
    """A guard that cannot fail is not a guard."""
    assert _violations("`<div>${user.name}</div>`")
    assert _violations('`<div class="${item.kind}">ok</div>`')
    # ...and does not cry wolf over the safe forms it must tolerate.
    assert not _violations("`<div>${esc(user.name)}</div>`")
    assert not _violations("`<b onclick='go(${attr(row.id)})'>x</b>`")
    assert not _violations("`<span>${refs.length} sources</span>`")
    assert not _violations("`<span>${(r.confidence * 100).toFixed(0)}%</span>`")
    assert not _violations("`<div>${fmtTs(seg.start_s)}</div>`")
    assert not _violations("`<i>${data.grounded ? 'yes' : 'no'}</i>`")


def test_escaping_helpers_are_defined_before_use() -> None:
    for name in ("const esc =", "const raw =", "const html ="):
        assert name in APP_JS, name
    # `html` must escape by default; `raw` is the only documented opt-out.
    assert "v.__html !== undefined" in APP_JS
    assert APP_JS.index("const esc =") < APP_JS.index("const html =")


def test_raw_is_never_applied_to_a_bare_property_access() -> None:
    """`raw(someObject.field)` would reintroduce exactly the hole `html` closes."""
    offenders = [
        m.group(0)
        for m in re.finditer(r"raw\(\s*[A-Za-z_$][\w$]*\s*\.\s*[\w$]+\s*\)", APP_JS)
    ]
    assert not offenders, f"raw() applied straight to fetched data: {offenders}"
