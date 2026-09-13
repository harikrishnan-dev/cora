from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from cora.agents.graph import build_graph
from cora.agents.refund import build_refund_agent
from cora.agents.triage.models import HelpdeskState
from cora.api.schemas import ChatRequest, ChatResponse, RefundRequest
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository

app = FastAPI(title="CORA", version="0.1.0")


@lru_cache(maxsize=1)
def _get_graph() -> CompiledStateGraph:
    return build_graph()


@lru_cache(maxsize=1)
def _get_refund_agent() -> CompiledStateGraph:
    return build_refund_agent(
        LLMRepository(), CommerceRepository(), checkpointer=InMemorySaver()
    )


def _is_paused(graph: CompiledStateGraph, config: dict) -> bool:
    """True if this thread is sitting at an `interrupt()` -- e.g. the
    refund specialist asked a clarifying question last turn. When paused,
    the next message must be sent as a `Command(resume=...)` instead of
    fresh graph input, or LangGraph restarts the thread instead of
    answering the pending question.
    """
    return bool(graph.get_state(config).next)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    config = {"configurable": {"thread_id": request.session_id}}
    graph = _get_graph()
    invoke_input = (
        Command(resume=request.message)
        if _is_paused(graph, config)
        else {"messages": [HumanMessage(content=request.message)], "info_complete": False}
    )
    raw_result = graph.invoke(invoke_input, config=config)

    if "__interrupt__" in raw_result:
        return ChatResponse(reply=raw_result["__interrupt__"][0].value)

    result = HelpdeskState.model_validate(raw_result)
    if result.refund_result:
        reply = result.refund_result
    elif result.shipping_delivery_result:
        reply = result.shipping_delivery_result
    elif result.classification_decision:
        # Classified, but that category's specialist node isn't wired up yet.
        reply = (
            f"Your request has been classified as {result.classification_decision.category} "
            f"(urgency: {result.classification_decision.urgency}) and routed to that team."
        )
    else:
        reply = result.messages[-1].content
    return ChatResponse(reply=reply)


@app.post("/refund/chat", response_model=ChatResponse)
def refund_chat(request: ChatRequest) -> ChatResponse:
    """Talk to the refund specialist directly, bypassing triage entirely.

    Same session_id/message shape as `/chat`, but the refund agent starts
    with none of product_id/customer_id/order_id known -- it gathers and
    verifies whatever it needs itself, via its own lookup tools.
    """
    config = {"configurable": {"thread_id": request.session_id}}
    agent = _get_refund_agent()
    invoke_input = (
        Command(resume=request.message)
        if _is_paused(agent, config)
        else {"messages": [HumanMessage(content=request.message)]}
    )
    result = agent.invoke(invoke_input, config=config)

    if "__interrupt__" in result:
        return ChatResponse(reply=result["__interrupt__"][0].value)
    return ChatResponse(reply=result["refund_result"])


@app.get("/refund-requests", response_model=list[RefundRequest])
def list_refund_requests(status: str | None = "pending") -> list[RefundRequest]:
    commerce_repository = CommerceRepository()
    return commerce_repository.list_refund_requests(status)


@app.post("/refund-requests/{request_id}/approve", response_model=RefundRequest)
def approve_refund_request(request_id: int) -> RefundRequest:
    commerce_repository = CommerceRepository()
    updated = commerce_repository.set_refund_request_status(request_id, "approved")
    if not updated:
        raise HTTPException(status_code=404, detail=f"No refund request with id {request_id}")
    return updated


@app.post("/refund-requests/{request_id}/reject", response_model=RefundRequest)
def reject_refund_request(request_id: int) -> RefundRequest:
    commerce_repository = CommerceRepository()
    updated = commerce_repository.set_refund_request_status(request_id, "rejected")
    if not updated:
        raise HTTPException(status_code=404, detail=f"No refund request with id {request_id}")
    return updated
