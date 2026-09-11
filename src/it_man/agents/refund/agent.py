from __future__ import annotations

from collections.abc import Callable

from langchain.agents import create_agent

from it_man.agents.common.commerce_tools import make_commerce_tools
from it_man.agents.refund.prompts import REFUND_PROMPT
from it_man.agents.refund.tools import make_refund_tools
from it_man.agents.state import HelpdeskState
from it_man.repository.commerce_repository import CommerceRepository
from it_man.repository.llm_repository import LLMRepository


def make_refund_node(
    llm_repository: LLMRepository, commerce_repository: CommerceRepository
) -> Callable[[HelpdeskState], dict]:
    tools = [*make_commerce_tools(commerce_repository), *make_refund_tools(commerce_repository)]
    agent = create_agent(
        llm_repository.get_model(), tools=tools, system_prompt=REFUND_PROMPT, name="refund"
    )

    def refund(state: HelpdeskState) -> dict:
        result = agent.invoke({"messages": state.messages})
        return {"messages": result["messages"]}

    return refund
