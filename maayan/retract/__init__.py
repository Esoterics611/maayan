"""Retraction: the eraser for layered knowledge (Prompt 17).

Adding knowledge is provenanced; so is removing it. A retraction is an attributed,
timestamped audit record — the chunk leaves retrieval, but the *fact that it was
retracted* is preserved. Only `expert` / `derived` / `term` chunks are retractable;
printed text (`sefaria` / `chabad`) is immutable and rejected in code.
"""
