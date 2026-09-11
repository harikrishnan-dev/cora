from __future__ import annotations

from collections.abc import Callable

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from it_man.agents.common.commerce_tools import make_commerce_tools
from it_man.agents.state import HelpdeskState
from it_man.agents.triage.models import ClassificationDecision, InfoGatheringDecision
from it_man.agents.triage.prompts import CLASSIFY_PROMPT, GATHER_INFO_PROMPT
from it_man.repository.commerce_repository import CommerceRepository
from it_man.repository.llm_repository import LLMRepository


def make_gather_info_node(
    llm_repository: LLMRepository, commerce_repository: CommerceRepository
) -> Callable[[HelpdeskState], dict]:
    """Build the `gather_info` node bound to a given `LLMRepository`/`CommerceRepository`.

    Taking the repositories as parameters (rather than constructing them at
    import time) lets `build_graph` decide which repository each node uses,
    and lets tests substitute fake/stub repositories.

    A single tool-calling agent handles both jobs in one call: it may call
    get_order_details/get_order_items/get_product_details/get_customer_details
    if the customer referenced an order, product, or customer code, and its
    `response_format=InfoGatheringDecision` forces the final answer into that
    schema regardless of how many tool calls it made along the way. Only the
    parsed decision is used -- the agent's own free-text messages are never
    added to `state`, so the customer only ever sees the clarifying question
    (if any).
    """
    agent = create_agent(
        llm_repository.get_model(),
        tools=make_commerce_tools(commerce_repository),
        system_prompt=GATHER_INFO_PROMPT,
        response_format=InfoGatheringDecision,
        name="gather_info",
    )

    def gather_info(state: HelpdeskState) -> dict:
        result = agent.invoke({"messages": state.messages})
        decision: InfoGatheringDecision = result["structured_response"]
        if not decision.info_complete:
            question = decision.clarifying_question or "Could you share a few more details?"
            return {"info_complete": False, "messages": [AIMessage(content=question)]}
        return {"info_complete": True}

    return gather_info


def make_classify_node(llm_repository: LLMRepository) -> Callable[[HelpdeskState], dict]:
    """Build the `classify` node bound to a given `LLMRepository`.

    Pure structured output, no tool-calling -- the category set is small and
    static, so a `Literal` field is more reliable than expecting the model
    to call a lookup tool for it.
    """
    prompt = ChatPromptTemplate.from_messages(
        [("system", CLASSIFY_PROMPT), ("placeholder", "{messages}")]
    )
    chain = prompt | llm_repository.get_model().with_structured_output(ClassificationDecision)

    def classify(state: HelpdeskState) -> dict:
        decision: ClassificationDecision = chain.invoke({"messages": state.messages})
        return {"category": decision.category, "urgency": decision.urgency}

    return classify
