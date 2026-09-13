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


class LLMDecision(BaseModel):
    decision: Union[FinalAnswer, ClarifyingQuestion]


class ShippingState(BaseModel):
    """State for the small `decide` <-> `ask_human` wrapper graph in
    `build_shipping_delivery_agent` -- not the decider itself, which uses
    `create_agent`'s own default state (it needs no injected top-level
    state, unlike refund's product_id, since every shipping tool takes
    order_code explicitly).

    pending_question is set by `decide` when the LLM's decision is a
    `ClarifyingQuestion`, and read by `ask_human` to know what to
    `interrupt()` with -- transient hand-off state between those two
    nodes, not part of the public result.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages] = []
    result: str | None = None
    pending_question: str | None = None
