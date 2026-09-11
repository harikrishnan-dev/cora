from __future__ import annotations

from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from cora.agents.common.commerce_tools import make_commerce_tools
from cora.agents.refund.models import ClarifyingQuestion, FinalAnswer, LLMDecision, RefundState
from cora.agents.refund.prompts import REFUND_PROMPT
from cora.agents.refund.tools import make_refund_tools
from cora.agents.triage.models import HelpdeskState
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository


def _build_refund_decider(
    llm_repository: LLMRepository, commerce_repository: CommerceRepository
) -> CompiledStateGraph:
    """The refund specialist's tool-calling agent. Runs its whole ReAct
    loop once per turn (get_refund_policy, is_already_refunded_or_not,
    initiate_refund, plus the shared commerce lookups) and forces its
    final answer into `LLMDecision` -- either a `FinalAnswer` or a
    `ClarifyingQuestion`. Wrapped by `build_refund_agent` below, which
    handles the `ClarifyingQuestion` case via `interrupt()`.
    """
    tools = [*make_commerce_tools(commerce_repository), *make_refund_tools(commerce_repository)]
    return create_agent(
        llm_repository.get_model(),
        tools=tools,
        system_prompt=REFUND_PROMPT,
        response_format=LLMDecision,
        state_schema=RefundState,
        name="refund_decider",
    )


def build_refund_agent(
    llm_repository: LLMRepository,
    commerce_repository: CommerceRepository,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the refund specialist as its own compiled agent (`RefundState`
    in/out), independent of the triage graph.

    Two nodes:
    - `decide` runs `_build_refund_decider`'s tool-calling agent once and
      reads off its `LLMDecision`. A `FinalAnswer` becomes
      `state.refund_result`; a `ClarifyingQuestion` is stashed in
      `state.pending_question` for `ask_human` to use.
    - `ask_human` calls `interrupt(state.pending_question)` to pause and
      surface the question, then appends the answer as a new message and
      loops back to `decide`.

    Splitting these into separate nodes (rather than looping inside one)
    matters: on resume, LangGraph only re-runs `ask_human`, never
    re-invokes `decide` for turns that were already answered -- looping
    inside a single node would re-run the LLM call on every resume.

    IMPORTANT: pass a `checkpointer` only when this is the top-level graph
    (e.g. `/refund/chat`). When nested inside `run_refund` for the triage
    graph, leave it unset -- an `interrupt()` here only pauses whichever
    graph is the innermost one with its own checkpointer, so giving this
    graph its own would swallow the interrupt instead of letting it
    propagate up to pause the OUTER (triage) graph.
    """
    decider = _build_refund_decider(llm_repository, commerce_repository)

    def decide(state: RefundState) -> RefundState:
        result = decider.invoke(
            {
                "messages": state.messages,
                "product_id": state.product_id,
                "customer_id": state.customer_id,
                "order_id": state.order_id,
            }
        )
        decision: LLMDecision = result["structured_response"]

        if isinstance(decision.decision, ClarifyingQuestion):
            state.pending_question = decision.decision.question
            return state

        answer: FinalAnswer = decision.decision
        state.pending_question = None
        state.refund_result = (
            f"Your refund request id is #{answer.refund_request_id}."
            if answer.refund_request_id is not None
            else "No refund request could be created for this order."
        )
        return state

    def route_after_decide(state: RefundState) -> str:
        return "ask_human" if state.pending_question else END

    def ask_human(state: RefundState) -> RefundState:
        answer = interrupt(state.pending_question)
        state.pending_question = None
        state.messages = answer
        return state

    graph = StateGraph(RefundState)
    graph.add_node("decide", decide)
    graph.add_node("ask_human", ask_human)
    graph.add_conditional_edges(
        "decide", route_after_decide, {"ask_human": "ask_human", END: END}
    )
    graph.add_edge("ask_human", "decide")
    graph.set_entry_point("decide")

    return graph.compile(checkpointer=checkpointer)


def run_refund(
    llm_repository: LLMRepository,
    commerce_repository: CommerceRepository,
    state: HelpdeskState,
) -> HelpdeskState:
    """Hand this ticket to the refund specialist: build it via
    `build_refund_agent` (no checkpointer -- see its docstring) and run it
    to completion. If it needs to ask a clarifying question, the
    `interrupt()` inside it propagates up through this call and pauses
    the OUTER (triage) graph instead, which does have a checkpointer.

    Registered as the triage graph's `refund` node directly -- see
    `graph.py`, which binds `llm_repository`/`commerce_repository` with
    `functools.partial` so the resulting callable matches the
    `state -> state` shape `add_node` expects, no separate node-factory
    wrapper needed.
    """
    agent = build_refund_agent(llm_repository, commerce_repository)
    query_details = state.query_details
    result = agent.invoke(
        {
            "messages": state.messages,
            "product_id": query_details.product_id if query_details else None,
            "customer_id": query_details.customer_id if query_details else None,
            "order_id": query_details.order_id if query_details else None,
        }
    )
    state.refund_result = result["refund_result"]
    return state
