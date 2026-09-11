from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from it_man.agents.graph import build_graph
from it_man.api.schemas import ChatRequest, ChatResponse, RefundRequest
from it_man.repository.commerce_repository import CommerceRepository

app = FastAPI(title="it-man", version="0.1.0")


@lru_cache(maxsize=1)
def _get_graph() -> CompiledStateGraph:
    return build_graph()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    config = {"configurable": {"thread_id": request.session_id}}
    result = _get_graph().invoke(
        {"messages": [HumanMessage(content=request.message)], "info_complete": False},
        config=config,
    )
    # Specialist nodes are disabled in agents/graph.py right now (debugging
    # triage in isolation), so once `classify` sets a category there's no
    # specialist reply to show -- summarize the routing decision instead.
    if result.get("category"):
        reply = (
            f"Your request has been classified as {result['category']} "
            f"(urgency: {result['urgency']}) and routed to that team."
        )
    else:
        reply = result["messages"][-1].content
    return ChatResponse(reply=reply)


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
