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
from cora.agents.warranty_service import run_warranty_service
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository

# category -> specialist node name. Only categories in here have a node
# registered below -- anything else falls through to END with just the
# classification decision recorded, rather than routing to a node that
# doesn't exist. Note "refund" is deliberately absent: it's no longer a
# classify-time destination -- it's only reached via warranty_service's
# handoff (see route_after_warranty_service).
_IMPLEMENTED_SPECIALISTS = {"shipping_delivery", "warranty_service"}


def route_after_gather(state: HelpdeskState) -> str:
    return "classify" if state.info_gathered.info_complete else END


def route_after_classify(state: HelpdeskState) -> str:
    category = state.classification_decision.category
    return category if category in _IMPLEMENTED_SPECIALISTS else END


def route_after_warranty_service(state: HelpdeskState) -> str:
    """warranty_service is the front door for any non-shipping ticket. If
    it decided the case isn't a covered warranty matter (no defect claim,
    or eligibility/coverage failed with no accepted paid repair), it sets
    `warranty_handoff_reason` and this sends the ticket on to `refund`
    next; otherwise warranty_service resolved it itself and the ticket
    ends here.
    """
    return "refund" if state.warranty_handoff_reason else END


def build_graph(
    llm_repository: LLMRepository | None = None,
    commerce_repository: CommerceRepository | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Build the customer-support graph.

    gather_info -> classify -> {shipping_delivery, warranty_service, END} -> END
                                                        |
                                                        v (if not a covered warranty matter)
                                                     refund -> END

    `classify` only decides the category; `route_after_classify` sends
    execution on to the matching specialist node via a conditional edge,
    or straight to `END` for any category without a specialist node yet.
    `warranty_service` is the front door for anything that isn't a shipping
    issue (a defect claim, or a plain refund request); if it decides the
    case isn't a covered warranty matter, `route_after_warranty_service`
    hands the ticket on to `refund` instead of ending there. `refund` is
    therefore never reached directly from `classify` -- only via that
    handoff (or the separate `/refund/chat` API endpoint, which bypasses
    this graph entirely).

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
    graph.add_node(
        "warranty_service", partial(run_warranty_service, llm_repository, commerce_repository)
    )

    graph.add_conditional_edges(
        "gather_info", route_after_gather, {"classify": "classify", END: END}
    )
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "shipping_delivery": "shipping_delivery",
            "warranty_service": "warranty_service",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "warranty_service", route_after_warranty_service, {"refund": "refund", END: END}
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
