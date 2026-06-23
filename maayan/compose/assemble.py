"""Assemble a Composition into a finished markdown document.

`assemble_markdown` is PURE and DETERMINISTIC given the same Composition + Brief (+ any
pre-generated transitions): title, then each section (heading + text), gap sections
clearly flagged as honest gaps, and a provenance FOOTER listing every cited ref, the
grounded-in set, the brief's author, and the model. The optional connective transitions
are generated upstream (in the service, behind `compose_transitions`) and passed in, so
this renderer never calls a model and is trivially testable.
"""

from __future__ import annotations

from collections.abc import Sequence

from maayan.compose.models import Brief, Composition

GAP_FLAG = "> **Honest gap** — the corpus is silent here; left empty rather than fabricated."


def assemble_markdown(
    composition: Composition,
    brief: Brief,
    *,
    transitions: Sequence[str] = (),
) -> str:
    """Render the composition as one markdown document with a provenance footer."""
    lines: list[str] = [
        f"# {brief.title}",
        "",
        f"*A {brief.content_type} grounded section-by-section in the corpus. "
        "Sections the sources don't reach are left as honest gaps, never fabricated.*",
        "",
    ]
    for i, section in enumerate(composition.sections):
        transition = transitions[i] if i < len(transitions) else ""
        if transition:
            lines += [f"*{transition.strip()}*", ""]
        lines.append(f"## {i + 1}. {section.heading}")
        lines.append("")
        if section.supported:
            lines.append(section.text.strip())
            if section.cited_refs:
                lines += ["", f"*Sources: {', '.join(section.cited_refs)}*"]
        else:
            lines += [GAP_FLAG, "", section.text.strip()]
        lines.append("")

    lines += _footer(composition, brief)
    return "\n".join(lines).rstrip() + "\n"


def _footer(composition: Composition, brief: Brief) -> list[str]:
    grounded = composition.supported_sections
    gaps = composition.gap_sections
    cited = ", ".join(composition.cited_refs) or "—"
    grounded_in = ", ".join(composition.grounded_in) or "—"
    return [
        "---",
        "",
        "### Provenance",
        "",
        f"- **Author:** {brief.author}",
        f"- **Model:** {composition.model}",
        f"- **Sections:** {grounded} grounded, {gaps} honest gap(s)",
        f"- **Cited sources:** {cited}",
        f"- **Grounded in (retrieved):** {grounded_in}",
        "",
        "_This is a grounded draft, not corpus. To feed knowledge back, promote a "
        "section's connection through the capture loop — never re-ingest this prose._",
    ]
