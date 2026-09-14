from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import APIKeyHeader
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from cora.agents.graph import build_graph
from cora.agents.refund import build_refund_agent
from cora.agents.triage.models import HelpdeskState
from cora.agents.warranty_service.catalog import get_coverage_policy, get_service_policy
from cora.api.schemas import (
    ChatRequest,
    ChatResponse,
    CustomerSummary,
    OrderSummary,
    ProductPolicy,
    ProductSummary,
    RefundRequest,
)
from cora.config import get_settings
from cora.repository.commerce_repository import CommerceRepository
from cora.repository.llm_repository import LLMRepository

app = FastAPI(title="CORA", version="0.1.0")

_admin_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_admin_key(api_key: str | None = Depends(_admin_api_key_header)) -> None:
    """Gate for staff-only endpoints (refund review): a shared secret sent
    via `X-API-Key`, checked in constant time so response timing can't leak
    how much of a guessed key matched.
    """
    settings = get_settings()
    if not api_key or not hmac.compare_digest(api_key, settings.admin_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


@lru_cache(maxsize=1)
def _get_checkpointer() -> PostgresSaver:
    """One shared Postgres-backed checkpointer for every graph in this
    process, so conversation state (paused interrupts included) survives
    process restarts -- unlike `InMemorySaver`, which loses it all on every
    redeploy. A `ConnectionPool` (not a single `Connection`) since FastAPI
    can run these sync endpoints from multiple worker threads at once, and
    a lone psycopg connection isn't safe to share across threads.

    `.setup()` creates this checkpointer's own tables -- idempotent, same
    spirit as bootstrap/seed.py's `CREATE TABLE IF NOT EXISTS`, safe to call
    on every boot.
    """
    settings = get_settings()
    pool = ConnectionPool(
        conninfo=settings.database_url,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    return checkpointer


@lru_cache(maxsize=1)
def _get_graph() -> CompiledStateGraph:
    return build_graph(checkpointer=_get_checkpointer())


@lru_cache(maxsize=1)
def _get_refund_agent() -> CompiledStateGraph:
    return build_refund_agent(
        LLMRepository(), CommerceRepository(), checkpointer=_get_checkpointer()
    )


def _is_paused(graph: CompiledStateGraph, config: dict) -> bool:
    """True if this thread is sitting at an `interrupt()` -- e.g. the
    refund specialist asked a clarifying question last turn. When paused,
    the next message must be sent as a `Command(resume=...)` instead of
    fresh graph input, or LangGraph restarts the thread instead of
    answering the pending question.
    """
    return bool(graph.get_state(config).next)


def _compute_session_token(session_id: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.session_secret.encode(), session_id.encode(), hashlib.sha256
    ).hexdigest()


def _authorize_session(graph: CompiledStateGraph, config: dict, request: ChatRequest) -> str:
    """Verify (or newly claim) ownership of `request.session_id`'s thread.

    A brand-new thread (no checkpoint yet -- `get_state().created_at is
    None`) has no owner yet, so it's claimed by whoever asks first: no
    token is required, and the caller gets one back to present on every
    later call. Once a thread has any checkpointed state, the caller MUST
    present the matching HMAC token or the request is rejected before the
    graph is ever invoked -- this is what stops a client that merely
    knows/guesses another session_id from resuming or answering a paused
    interrupt() on someone else's conversation.
    """
    expected_token = _compute_session_token(request.session_id)
    is_new_thread = graph.get_state(config).created_at is None

    if not is_new_thread and (
        not request.session_token or not hmac.compare_digest(request.session_token, expected_token)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid session token")

    return expected_token


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    config = {"configurable": {"thread_id": request.session_id}}
    graph = _get_graph()
    session_token = _authorize_session(graph, config, request)
    invoke_input = (
        Command(resume=request.message)
        if _is_paused(graph, config)
        else {"messages": [HumanMessage(content=request.message)], "info_complete": False}
    )
    raw_result = graph.invoke(invoke_input, config=config)

    if "__interrupt__" in raw_result:
        return ChatResponse(reply=raw_result["__interrupt__"][0].value, session_token=session_token)

    result = HelpdeskState.model_validate(raw_result)
    if result.refund_result:
        reply = result.refund_result
    elif result.shipping_delivery_result:
        reply = result.shipping_delivery_result
    elif result.warranty_service_result:
        reply = result.warranty_service_result
    elif result.classification_decision:
        # Classified, but that category's specialist node isn't wired up yet.
        reply = (
            f"Your request has been classified as {result.classification_decision.category} "
            f"(urgency: {result.classification_decision.urgency}) and routed to that team."
        )
    else:
        reply = result.messages[-1].content
    return ChatResponse(reply=reply, session_token=session_token)


@app.post("/refund/chat", response_model=ChatResponse)
def refund_chat(request: ChatRequest) -> ChatResponse:
    """Talk to the refund specialist directly, bypassing triage entirely.

    Same session_id/message shape as `/chat`, but the refund agent starts
    with none of product_id/customer_id/order_id known -- it gathers and
    verifies whatever it needs itself, via its own lookup tools.
    """
    config = {"configurable": {"thread_id": request.session_id}}
    agent = _get_refund_agent()
    session_token = _authorize_session(agent, config, request)
    invoke_input = (
        Command(resume=request.message)
        if _is_paused(agent, config)
        else {"messages": [HumanMessage(content=request.message)]}
    )
    result = agent.invoke(invoke_input, config=config)

    if "__interrupt__" in result:
        return ChatResponse(reply=result["__interrupt__"][0].value, session_token=session_token)
    return ChatResponse(reply=result["refund_result"], session_token=session_token)


@app.get(
    "/refund-requests", response_model=list[RefundRequest], dependencies=[Depends(require_admin_key)]
)
def list_refund_requests(status: str | None = "pending") -> list[RefundRequest]:
    commerce_repository = CommerceRepository()
    return commerce_repository.list_refund_requests(status)


@app.post(
    "/refund-requests/{request_id}/approve",
    response_model=RefundRequest,
    dependencies=[Depends(require_admin_key)],
)
def approve_refund_request(request_id: int) -> RefundRequest:
    commerce_repository = CommerceRepository()
    updated = commerce_repository.set_refund_request_status(request_id, "approved")
    if not updated:
        raise HTTPException(status_code=404, detail=f"No refund request with id {request_id}")
    return updated


@app.post(
    "/refund-requests/{request_id}/reject",
    response_model=RefundRequest,
    dependencies=[Depends(require_admin_key)],
)
def reject_refund_request(request_id: int) -> RefundRequest:
    commerce_repository = CommerceRepository()
    updated = commerce_repository.set_refund_request_status(request_id, "rejected")
    if not updated:
        raise HTTPException(status_code=404, detail=f"No refund request with id {request_id}")
    return updated


@app.get("/orders", response_model=list[OrderSummary], dependencies=[Depends(require_admin_key)])
def list_orders() -> list[OrderSummary]:
    return CommerceRepository().list_orders()


@app.get(
    "/customers", response_model=list[CustomerSummary], dependencies=[Depends(require_admin_key)]
)
def list_customers() -> list[CustomerSummary]:
    return CommerceRepository().list_customers()


@app.get(
    "/products", response_model=list[ProductSummary], dependencies=[Depends(require_admin_key)]
)
def list_products() -> list[ProductSummary]:
    return CommerceRepository().list_products()


@app.get(
    "/products/{sku}/policy",
    response_model=ProductPolicy,
    dependencies=[Depends(require_admin_key)],
)
def get_product_policy(sku: str) -> ProductPolicy:
    product = CommerceRepository().get_product(sku)
    if not product:
        raise HTTPException(status_code=404, detail=f"No product with sku {sku}")
    return ProductPolicy(
        **product,
        coverage=get_coverage_policy(product["category"]),
        service=get_service_policy(product["category"]),
    )
