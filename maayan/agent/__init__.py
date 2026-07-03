"""The chavrusa agent (Phase 7, Prompt 39): a bounded multi-hop study loop.

The harness centerpiece: a small, safe, typed action space (search / open a
section / walk the graph / look up a term / conclude) with hard budgets, driven
by plain completion + strict JSON parsing so every backend is eligible. The
capability lives in the tools and the verifiers, never in prompt cleverness —
a better model dropped into the same loop simply studies better, and that
delta is the product.
"""
