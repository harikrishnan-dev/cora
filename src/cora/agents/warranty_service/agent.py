from __future__ import annotations

from collections.abc import Callable

from langchain.agents import create_agent

from cora.agents.common.commerce_tools import make_commerce_tools
from cora.agents.state import HelpdeskState
from cora.agents.warranty_service.prompts import WARRANTY_SERVICE_PROMPT
from cora.agents.warranty_service.tools import make_warranty_service_tools
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository


def make_warranty_service_node(
    llm_repository: LLMRepository, commerce_repository: CommerceRepository
) -> Callable[[HelpdeskState], dict]:
    tools = [
        *make_commerce_tools(commerce_repository),
        *make_warranty_service_tools(commerce_repository),
    ]
    agent = create_agent(
        llm_repository.get_model(),
        tools=tools,
        system_prompt=WARRANTY_SERVICE_PROMPT,
        name="warranty_service",
    )

    def warranty_service(state: HelpdeskState) -> dict:
        result = agent.invoke({"messages": state.messages})
        return {"messages": result["messages"]}

    return warranty_service
