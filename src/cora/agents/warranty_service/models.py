from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Union

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class FinalAnswer(BaseModel):
    """Use when you have enough information to answer."""

    message: str


class ClarifyingQuestion(BaseModel):
    """Use when the request is ambiguous or missing details."""

    question: str


class ForwardToRefund(BaseModel):
    """Use ONLY for: (1) a genuine, in-warranty defect whose category isn't
    practical to repair or replace in-house (decide_repair_vs_replace
    returned "refund"), or (2) no defect at all -- a plain refund request
    that this store's return policy allows. NEVER use this for a claim that
    fails eligibility (expired warranty) or coverage (an excluded,
    non-genuine cause like accidental damage) -- deny those with
    FinalAnswer instead."""

    reason: str


class LLMDecision(BaseModel):
    decision: Union[FinalAnswer, ClarifyingQuestion, ForwardToRefund]


class WarrantyState(BaseModel):
    """State for the small `decide` <-> `ask_human` wrapper graph in
    `build_warranty_service_agent` -- not the decider itself, which uses
    `create_agent`'s own default state (it needs no injected top-level
    state, since every warranty tool takes order_code/sku explicitly).

    pending_question is set by `decide` when the LLM's decision is a
    `ClarifyingQuestion`, and read by `ask_human` to know what to
    `interrupt()` with -- transient hand-off state between those two
    nodes, not part of the public result.

    forward_reason is set by `decide` when the LLM's decision is a
    `ForwardToRefund` -- read by `run_warranty_service` to hand the ticket
    off to the refund specialist instead of resolving it here.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages] = []
    result: str | None = None
    pending_question: str | None = None
    forward_reason: str | None = None
