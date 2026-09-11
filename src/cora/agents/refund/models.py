from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Union

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class FinalAnswer(BaseModel):
    """Use when you have enough information to answer."""

    refund_request_id: int | None = None


class ClarifyingQuestion(BaseModel):
    """Use when the request is ambiguous or missing details."""

    question: str


class LLMDecision(BaseModel):
    decision: Union[FinalAnswer, ClarifyingQuestion]


class RefundState(BaseModel):
    """State for the refund agent, standalone or as a node in the triage graph.

    product_id/customer_id/order_id sit at the top level (not nested, unlike
    triage's QueryDetails) because get_refund_policy reads product_id via
    InjectedState -- LangGraph resolves that against a top-level state key.
    All three are optional: triage seeds whatever it already validated, and
    a customer talking to this agent directly starts with none of them known.

    pending_question is set by the `decide` node in `build_refund_agent`
    when the LLM's decision is a `ClarifyingQuestion`, and read by the
    `ask_human` node to know what to `interrupt()` with -- it's transient
    hand-off state between those two nodes, not part of the public result.

    structured_response must be declared here even though `decide` never
    reads or writes it directly: this is also the `state_schema` passed to
    `create_agent` for the inner tool-calling agent (`_build_refund_decider`),
    and `create_agent` writes its `response_format` output to a
    `structured_response` key on whatever state schema it's given. A
    pydantic `state_schema` silently drops any key a node returns that
    isn't declared as a field -- so without this, `result["structured_response"]`
    in `decide()` raises `KeyError` instead of returning the `LLMDecision`.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages] = []
    product_id: str | None = None
    customer_id: str | None = None
    order_id: str | None = None
    refund_result: str | None = None
    pending_question: str | None = None
    structured_response: LLMDecision | None = None
