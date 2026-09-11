from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from cora.agents.state import HelpdeskState
from cora.agents.triage import make_classify_node, make_gather_info_node
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository

CATEGORY_TO_SPECIALIST = {
    "refund": "refund",
    "warranty_service": "warranty_service",
    "shipping_delivery": "shipping_delivery",
    "order_change": "order_changes",
}


def route_after_gather(state: HelpdeskState) -> str:
    return "classify" if state.info_complete else END


def route_after_classify(state: HelpdeskState) -> str:
    return CATEGORY_TO_SPECIALIST[state.category]


def build_graph(
    llm_repository: LLMRepository | None = None,
    commerce_repository: CommerceRepository | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the customer-support graph.

    gather_info -> classify -> {refund, warranty_service, shipping_delivery,
    order_changes} -> END

    Both repositories default to real, Postgres/Anthropic-backed instances, but
    accepting them as parameters means this is the single place that
    decides which repository each node uses -- callers (tests included) can
    pass in a fake/stub repository instead.

    Compiled with a checkpointer so conversation state (messages,
    info_complete, category, urgency) persists across `.invoke()` calls for
    the same `thread_id` -- callers only need to send the latest message,
    not the full history. Defaults to `InMemorySaver` (in-process, lost on
    restart); pass a different `BaseCheckpointSaver` to persist elsewhere.
    """
    llm_repository = llm_repository or LLMRepository()
    commerce_repository = commerce_repository or CommerceRepository()
    checkpointer = checkpointer or InMemorySaver()

    graph = StateGraph(HelpdeskState)

    graph.add_node(
        "gather_info", make_gather_info_node(llm_repository, commerce_repository)
    )
    graph.add_node("classify", make_classify_node(llm_repository))
    # graph.add_node("refund", make_refund_node(llm_repository, commerce_repository))
    # graph.add_node(
    #     "warranty_service", make_warranty_service_node(llm_repository, commerce_repository)
    # )
    # graph.add_node(
    #     "shipping_delivery", make_shipping_delivery_node(llm_repository, commerce_repository)
    # )
    # graph.add_node("order_changes", make_order_changes_node(llm_repository, commerce_repository))

    graph.add_conditional_edges(
        "gather_info", route_after_gather, {"classify": "classify", END: END}
    )
    # graph.add_conditional_edges(
    #     "classify",
    #     route_after_classify,
    #     {
    #         "refund": "refund",
    #         "warranty_service": "warranty_service",
    #         "shipping_delivery": "shipping_delivery",
    #         "order_changes": "order_changes",
    #     },
    # )
    # for specialist in ("refund", "warranty_service", "shipping_delivery", "order_changes"):
    #     graph.add_edge(specialist, END)

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
