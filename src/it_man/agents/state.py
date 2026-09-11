from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class HelpdeskState(BaseModel):
    """Shared state passed between nodes in the customer-support graph."""

    messages: Annotated[Sequence[BaseMessage], add_messages] = []
    info_complete: bool = False
    category: str | None = None
    urgency: str | None = None
