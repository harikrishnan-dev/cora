from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class InfoGatheringDecision(BaseModel):
    info_complete: bool
    clarifying_question: str | None = None
    product_id: str | None = None
    customer_id: str | None = None
    order_id: str | None = None


class ClassificationDecision(BaseModel):
    category: Literal["refund", "warranty_service", "shipping_delivery", "order_change"]
    urgency: Literal["low", "medium", "high", "critical"]


class QueryDetails(BaseModel):
    product_id: str | None = None
    customer_id: str | None = None
    order_id: str | None = None


class HelpdeskState(BaseModel):
    """Shared state passed between nodes in the customer-support graph."""

    messages: Annotated[Sequence[BaseMessage], add_messages] = []
    info_gathered: InfoGatheringDecision | None = None
    classification_decision: ClassificationDecision | None = None
    compacted_message: str | None  = None
    query_details: QueryDetails | None = None
    refund_result: str | None = None

