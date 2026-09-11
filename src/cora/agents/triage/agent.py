from __future__ import annotations

from collections.abc import Callable

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from cora.agents.common.commerce_tools import make_commerce_tools

from cora.agents.triage.models import HelpdeskState
from cora.agents.triage.models import ClassificationDecision, InfoGatheringDecision, QueryDetails
from cora.agents.triage.prompts import CLASSIFY_PROMPT, GATHER_INFO_PROMPT
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository


def make_gather_info_node(
    llm_repository: LLMRepository, commerce_repository: CommerceRepository
) -> Callable[[HelpdeskState], HelpdeskState]:
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

    def gather_info(state: HelpdeskState) -> HelpdeskState:
        result = agent.invoke({"messages": state.messages})
        decision: InfoGatheringDecision = result["structured_response"]

        product_id = decision.product_id
        if product_id and not commerce_repository.get_product(product_id):
            product_id = None

        customer_id = decision.customer_id
        if customer_id and not commerce_repository.get_customer(customer_id):
            customer_id = None

        order_id = decision.order_id
        if order_id and not commerce_repository.get_order(order_id):
            order_id = None

        state.query_details = QueryDetails(
            product_id=product_id, customer_id=customer_id, order_id=order_id
        )

        # The LLM may have called the lookup tools and still hallucinated or
        # mistyped a code in its final answer -- re-check every identifier it
        # reported against the repository directly rather than trusting that
        # it validated itself, and treat a code that doesn't exist the same
        # as one that was never provided.
        invalid = [
            label
            for label, raw, validated in (
                ("product", decision.product_id, product_id),
                ("order", decision.order_id, order_id),
                ("customer", decision.customer_id, customer_id),
            )
            if raw and not validated
        ]

        if invalid or not decision.info_complete:
            question = decision.clarifying_question
            if invalid and not question:
                question = (
                    f"I couldn't find a {invalid[0]} matching what you gave me -- "
                    "could you double-check it?"
                )
            question = question or "Could you share a few more details?"
            state.info_gathered = InfoGatheringDecision(info_complete=False, clarifying_question=question)
            state.messages = question
            return state

        state.info_gathered = InfoGatheringDecision(info_complete=True)
        return state


    return gather_info


def make_classify_node(llm_repository: LLMRepository) -> Callable[[HelpdeskState], HelpdeskState]:
    """Build the `classify` node bound to a given `LLMRepository`.

    Pure structured output, no tool-calling -- the category set is small and
    static, so a `Literal` field is more reliable than expecting the model
    to call a lookup tool for it.

    Only decides and records the category -- dispatch to the matching
    specialist (e.g. `refund`) is a separate graph node reached via a
    conditional edge in `graph.py`, not something this node does itself.
    """
    prompt = ChatPromptTemplate.from_messages(
        [("system", CLASSIFY_PROMPT), ("placeholder", "{messages}")]
    )
    chain = prompt | llm_repository.get_model().with_structured_output(ClassificationDecision)

    def classify(state: HelpdeskState) -> HelpdeskState:
        decision: ClassificationDecision = chain.invoke({"messages": state.messages})
        state.classification_decision = decision
        return state

    return classify
