from __future__ import annotations

from functools import partial

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cora.agents.triage.models import HelpdeskState
from cora.agents.triage import make_classify_node, make_gather_info_node
from cora.agents.refund import run_refund
from cora.agents.shipping_delivery import run_shipping_delivery
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository

# category -> specialist node name. Only categories in here have a node
# registered below -- anything else falls through to END with just the
# classification decision recorded, rather than routing to a node that
# doesn't exist.
_IMPLEMENTED_SPECIALISTS = {"refund", "shipping_delivery"}


def route_after_gather(state: HelpdeskState) -> str:
    return "classify" if state.info_gathered.info_complete else END


def route_after_classify(state: HelpdeskState) -> str:
    category = state.classification_decision.category
    return category if category in _IMPLEMENTED_SPECIALISTS else END


def build_graph(
    llm_repository: LLMRepository | None = None,
    commerce_repository: CommerceRepository | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the customer-support graph.

    gather_info -> classify -> {refund, shipping_delivery, END} -> END

    `classify` only decides the category; `route_after_classify` sends
    execution on to the matching specialist node via a conditional edge,
    or straight to `END` for any category without a specialist node yet.

    Compiled with a checkpointer so conversation state (messages,
    info_complete, category, urgency) persists across `.invoke()` calls for
    the same `thread_id` -- callers only need to send the latest message,
    not the full history. Defaults to `InMemorySaver` (in-process, lost on
    restart); pass a different `BaseCheckpointSaver` to persist elsewhere.
    """
    llm_repository = llm_repository or LLMRepository()
    commerce_repository = commerce_repository or CommerceRepository()
    checkpointer = checkpointer or InMemorySaver()

    graph = StateGraph[HelpdeskState, None, HelpdeskState, HelpdeskState](HelpdeskState)

    graph.add_node(
        "gather_info", make_gather_info_node(llm_repository, commerce_repository)
    )
    graph.add_node("classify", make_classify_node(llm_repository))
    graph.add_node("refund", partial(run_refund, llm_repository, commerce_repository))
    graph.add_node(
        "shipping_delivery", partial(run_shipping_delivery, llm_repository, commerce_repository)
    )

    graph.add_conditional_edges(
        "gather_info", route_after_gather, {"classify": "classify", END: END}
    )
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"refund": "refund", "shipping_delivery": "shipping_delivery", END: END},
    )
    graph.add_edge("refund", END)
    graph.add_edge("shipping_delivery", END)

    graph.set_entry_point("gather_info")

    return graph.compile(checkpointer=checkpointer)


def load_graph() -> CompiledStateGraph:
    """Zero-arg factory for `langgraph.json` (the LangGraph CLI/Platform).

    The CLI's graph loader requires a factory with 0, 1, or 2 parameters and
    checks the parameter count directly, ignoring defaults -- so it rejects
    `build_graph` (3 params, kept for dependency injection in tests). This
    thin wrapper is what `langgraph.json` points at instead.
    """
    return build_graph()
