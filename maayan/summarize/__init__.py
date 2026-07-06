"""Gated section summaries (Prompt 42): RAPTOR-lite, exactly one level.

`maayan summarize` drafts one grounded, faithfulness-checked summary per chapter/section
(drip-paced, proposed → approved gate like develop). Approved summaries index as
``source="summary"`` chunks whose metadata carries the parent ref and the child refs, so
a conceptual query can land on a chapter summary and the apparatus leads down into the
exact osiyos. Summary chunks are retractable; printed text is untouched.
"""
