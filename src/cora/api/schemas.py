from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str


class RefundRequest(BaseModel):
    id: int
    order_code: str
    amount_cents: int
    reason: str | None
    status: str
    requested_at: datetime
    resolved_at: datetime | None
