"""Composition: from grounded answers to grounded documents (Phase 5).

A composition turns a single brief into a structured, multi-section document — a
shiur/class outline first — by running the existing grounded unit (retrieve →
default-deny gate → one cited block) ONCE PER SECTION. It is an orchestration layer,
not a new generation engine: the corpus grounds the piece section-by-section, and an
unsupported section becomes an honest gap rather than fabricated prose.
"""
