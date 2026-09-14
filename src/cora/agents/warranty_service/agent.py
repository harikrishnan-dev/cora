from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from cora.agents.common.commerce_tools import make_commerce_tools
from cora.agents.triage.models import HelpdeskState
from cora.agents.warranty_service.models import (
    ClarifyingQuestion,
    FinalAnswer,
    ForwardToRefund,
    LLMDecision,
    WarrantyState,
)
from cora.agents.warranty_service.prompts import WARRANTY_SERVICE_PROMPT
from cora.agents.warranty_service.tools import make_warranty_service_tools
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository


def _build_warranty_service_decider(
    llm_repository: LLMRepository, commerce_repository: CommerceRepository
) -> CompiledStateGraph:
    """The warranty specialist's tool-calling agent. Runs its whole ReAct
    loop once per turn (check_warranty_eligibility, decide_repair_vs_replace,
    estimate_repair_cost, create_service_ticket, plus the shared commerce
    lookups) and forces its final answer into `LLMDecision` -- either a
    `FinalAnswer` or a `ClarifyingQuestion`. No custom state schema needed --
    unlike refund, no tool here reads injected top-level state (every tool
    takes order_code/sku explicitly), so `create_agent`'s own default state
    already has everything (including `structured_response`) that's needed.
    """
    tools = [
        *make_commerce_tools(commerce_repository),
        *make_warranty_service_tools(commerce_repository),
    ]
    return create_agent(
        llm_repository.get_model(),
        tools=tools,
        system_prompt=WARRANTY_SERVICE_PROMPT,
        response_format=LLMDecision,
        name="warranty_service_decider",
    )


def build_warranty_service_agent(
    llm_repository: LLMRepository,
    commerce_repository: CommerceRepository,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the warranty & service specialist as its own compiled agent,
    following the same `decide` <-> `ask_human` interrupt pattern as
    `refund.build_refund_agent` and
    `shipping_delivery.build_shipping_delivery_agent`:

    - `decide` runs `_build_warranty_service_decider` once and reads off its
      `LLMDecision`. A `FinalAnswer` becomes `state.result`; a
      `ClarifyingQuestion` is stashed in `state.pending_question`; a
      `ForwardToRefund` is stashed in `state.forward_reason` for
      `run_warranty_service` to hand the ticket off to Refund.
    - `ask_human` calls `interrupt(state.pending_question)` to pause and
      surface the question, then appends the answer and loops back to
      `decide`.

    Two nodes rather than one loop: on resume, LangGraph only re-runs
    `ask_human`, never re-invokes the LLM for turns already answered.

    IMPORTANT: pass a `checkpointer` only when this is the top-level graph.
    When nested inside `run_warranty_service` for the triage graph, leave it
    unset so an `interrupt()` here propagates up to pause the OUTER (triage)
    graph instead of being caught at this level.
    """
    decider = _build_warranty_service_decider(llm_repository, commerce_repository)

    def decide(state: WarrantyState) -> WarrantyState:
        result = decider.invoke({"messages": state.messages})
        decision: LLMDecision = result["structured_response"]

        if isinstance(decision.decision, ClarifyingQuestion):
            state.pending_question = decision.decision.question
            return state

        state.pending_question = None

        if isinstance(decision.decision, ForwardToRefund):
            state.forward_reason = decision.decision.reason
            return state

        answer: FinalAnswer = decision.decision
        state.result = answer.message
        return state

    def route_after_decide(state: WarrantyState) -> str:
        return "ask_human" if state.pending_question else END

    def ask_human(state: WarrantyState) -> WarrantyState:
        answer = interrupt(state.pending_question)
        state.pending_question = None
        state.messages = answer
        return state

    graph = StateGraph(WarrantyState)
    graph.add_node("decide", decide)
    graph.add_node("ask_human", ask_human)
    graph.add_conditional_edges(
        "decide", route_after_decide, {"ask_human": "ask_human", END: END}
    )
    graph.add_edge("ask_human", "decide")
    graph.set_entry_point("decide")

    return graph.compile(checkpointer=checkpointer)


def run_warranty_service(
    llm_repository: LLMRepository,
    commerce_repository: CommerceRepository,
    state: HelpdeskState,
) -> HelpdeskState:
    """Hand this ticket to the warranty & service specialist.

    If it resolves the case itself, its reply lands in
    `state.warranty_service_result`. If it decides this isn't a covered
    warranty matter, `state.warranty_handoff_reason` is set instead --
    `graph.py`'s `route_after_warranty_service` reads that to send the
    ticket on to the `refund` node next, in the same graph run. The
    handoff reason is also appended to `state.messages` as an `AIMessage`
    (via the same `add_messages`-reducer idiom `ask_human` uses) so the
    refund specialist sees why it received this ticket, instead of
    starting from nothing.

    If warranty needs to ask a clarifying question, the `interrupt()`
    inside it propagates up through this call and pauses the OUTER
    (triage) graph, which does have a checkpointer -- so the next message
    resumes exactly here instead of re-running gather_info/classify from
    scratch.

    Registered as the triage graph's `warranty_service` node directly --
    see `graph.py`, which binds `llm_repository`/`commerce_repository` with
    `functools.partial` so the resulting callable matches the
    `state -> state` shape `add_node` expects.
    """
    agent = build_warranty_service_agent(llm_repository, commerce_repository)
    result = agent.invoke({"messages": state.messages})
    if result.get("forward_reason"):
        state.warranty_handoff_reason = result["forward_reason"]
        state.messages = [
            AIMessage(
                content=(
                    f"[Warranty & Service]: {result['forward_reason']} "
                    "Routing this to Refund."
                )
            )
        ]
    else:
        state.warranty_service_result = result["result"]
    return state
