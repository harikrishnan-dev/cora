from __future__ import annotations

from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from cora.agents.common.commerce_tools import make_commerce_tools
from cora.agents.shipping_delivery.models import (
    ClarifyingQuestion,
    FinalAnswer,
    LLMDecision,
    ShippingState,
)
from cora.agents.shipping_delivery.prompts import SHIPPING_DELIVERY_PROMPT
from cora.agents.shipping_delivery.tools import make_shipping_tools
from cora.agents.triage.models import HelpdeskState
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository


def _build_shipping_decider(
    llm_repository: LLMRepository, commerce_repository: CommerceRepository
) -> CompiledStateGraph:
    """The shipping specialist's tool-calling agent. Runs its whole ReAct
    loop once per turn (get_order_details/get_order_items for lookups,
    update_shipping_address for address changes) and forces its final
    answer into `LLMDecision` -- either a `FinalAnswer` or a
    `ClarifyingQuestion`. No custom state schema needed -- unlike refund,
    no tool here reads injected top-level state (every tool takes
    order_code explicitly), so `create_agent`'s own default state already
    has everything (including `structured_response`) that's needed.
    """
    tools = [*make_commerce_tools(commerce_repository), *make_shipping_tools(commerce_repository)]
    return create_agent(
        llm_repository.get_model(),
        tools=tools,
        system_prompt=SHIPPING_DELIVERY_PROMPT,
        response_format=LLMDecision,
        name="shipping_delivery_decider",
    )


def build_shipping_delivery_agent(
    llm_repository: LLMRepository,
    commerce_repository: CommerceRepository,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the shipping & delivery specialist as its own compiled agent,
    following the same `decide` <-> `ask_human` interrupt pattern as
    `refund.build_refund_agent`:

    - `decide` runs `_build_shipping_decider` once and reads off its
      `LLMDecision`. A `FinalAnswer` becomes `state.result`; a
      `ClarifyingQuestion` is stashed in `state.pending_question`.
    - `ask_human` calls `interrupt(state.pending_question)` to pause and
      surface the question, then appends the answer and loops back to
      `decide`.

    Two nodes rather than one loop: on resume, LangGraph only re-runs
    `ask_human`, never re-invokes the LLM for turns already answered.

    IMPORTANT: pass a `checkpointer` only when this is the top-level graph.
    When nested inside `run_shipping_delivery` for the triage graph, leave
    it unset so an `interrupt()` here propagates up to pause the OUTER
    (triage) graph instead of being caught at this level.
    """
    decider = _build_shipping_decider(llm_repository, commerce_repository)

    def decide(state: ShippingState) -> ShippingState:
        result = decider.invoke({"messages": state.messages})
        decision: LLMDecision = result["structured_response"]

        if isinstance(decision.decision, ClarifyingQuestion):
            state.pending_question = decision.decision.question
            return state

        answer: FinalAnswer = decision.decision
        state.pending_question = None
        state.result = answer.message
        return state

    def route_after_decide(state: ShippingState) -> str:
        return "ask_human" if state.pending_question else END

    def ask_human(state: ShippingState) -> ShippingState:
        answer = interrupt(state.pending_question)
        state.pending_question = None
        state.messages = answer
        return state

    graph = StateGraph(ShippingState)
    graph.add_node("decide", decide)
    graph.add_node("ask_human", ask_human)
    graph.add_conditional_edges(
        "decide", route_after_decide, {"ask_human": "ask_human", END: END}
    )
    graph.add_edge("ask_human", "decide")
    graph.set_entry_point("decide")

    return graph.compile(checkpointer=checkpointer)


def run_shipping_delivery(
    llm_repository: LLMRepository,
    commerce_repository: CommerceRepository,
    state: HelpdeskState,
) -> HelpdeskState:
    """Hand this ticket to the shipping & delivery specialist and fold its
    reply into `state.shipping_delivery_result`. If it needs to ask a
    clarifying question, the `interrupt()` inside it propagates up through
    this call and pauses the OUTER (triage) graph, which does have a
    checkpointer -- so the next message resumes exactly here instead of
    re-running gather_info/classify from scratch.

    Registered as the triage graph's `shipping_delivery` node directly --
    see `graph.py`, which binds `llm_repository`/`commerce_repository` with
    `functools.partial` so the resulting callable matches the
    `state -> state` shape `add_node` expects.
    """
    agent = build_shipping_delivery_agent(llm_repository, commerce_repository)
    result = agent.invoke({"messages": state.messages})
    state.shipping_delivery_result = result["result"]
    return state
