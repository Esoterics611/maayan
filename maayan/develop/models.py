"""Model for a seed development — a PROPOSAL until an expert approves it.

A `Development` is the model's grounded elaboration of an expert seed under its
directive. It is *not* corpus: it carries `status` (proposed → approved/rejected,
Prompt 13) and `grounded` (False = the develop step honestly refused because the
corpus doesn't support the seed). Provenance travels with it: which seed, whose
seed, which thread, which model, and the refs it was grounded on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# "retracted" is set when an approved (indexed) development is later retracted
# (Prompt 17): the derived chunk leaves retrieval and the development is tombstoned.
DevelopmentStatus = Literal["proposed", "approved", "rejected", "retracted"]


class Development(BaseModel):
    """A grounded development of a seed (or an honest refusal), with full provenance."""

    id: str
    thread_id: str
    seed_id: str
    author: str  # the seed's author (carried so a derived chunk can attribute it, Prompt 13)
    timestamp: datetime
    model: str  # generation model id; "" when refused (no model call was made)
    status: DevelopmentStatus = "proposed"
    grounded: bool = True  # False → honest refusal: the corpus does not support the seed
    text: str
    cited_refs: list[str] = Field(default_factory=list)  # refs the development actually cited
    grounded_in: list[str] = Field(default_factory=list)  # the refs retrieved for it
