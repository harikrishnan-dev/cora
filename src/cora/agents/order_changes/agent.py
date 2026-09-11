from __future__ import annotations

from collections.abc import Callable

from langchain.agents import create_agent

from cora.agents.common.commerce_tools import make_commerce_tools
from cora.agents.order_changes.prompts import ORDER_CHANGES_PROMPT
from cora.agents.order_changes.tools import make_order_changes_tools
from cora.agents.state import HelpdeskState
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository


def make_order_changes_node(
    llm_repository: LLMRepository, commerce_repository: CommerceRepository
) -> Callable[[HelpdeskState], dict]:
    tools = [
        *make_commerce_tools(commerce_repository),
        *make_order_changes_tools(commerce_repository),
    ]
    agent = create_agent(
        llm_repository.get_model(),
        tools=tools,
        system_prompt=ORDER_CHANGES_PROMPT,
        name="order_changes",
    )

    def order_changes(state: HelpdeskState) -> dict:
        result = agent.invoke({"messages": state.messages})
        return {"messages": result["messages"]}

    return order_changes
