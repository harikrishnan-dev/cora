from __future__ import annotations

from collections.abc import Callable

from langchain.agents import create_agent

from it_man.agents.common.commerce_tools import make_commerce_tools
from it_man.agents.shipping_delivery.prompts import SHIPPING_DELIVERY_PROMPT
from it_man.agents.shipping_delivery.tools import make_shipping_delivery_tools
from it_man.agents.state import HelpdeskState
from it_man.repository.commerce_repository import CommerceRepository
from it_man.repository.llm_repository import LLMRepository


def make_shipping_delivery_node(
    llm_repository: LLMRepository, commerce_repository: CommerceRepository
) -> Callable[[HelpdeskState], dict]:
    tools = [
        *make_commerce_tools(commerce_repository),
        *make_shipping_delivery_tools(commerce_repository),
    ]
    agent = create_agent(
        llm_repository.get_model(),
        tools=tools,
        system_prompt=SHIPPING_DELIVERY_PROMPT,
        name="shipping_delivery",
    )

    def shipping_delivery(state: HelpdeskState) -> dict:
        result = agent.invoke({"messages": state.messages})
        return {"messages": result["messages"]}

    return shipping_delivery
