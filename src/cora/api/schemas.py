from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str
    session_token: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_token: str


class RefundRequest(BaseModel):
    id: int
    order_code: str
    amount_cents: int
    reason: str | None
    status: str
    requested_at: datetime
    resolved_at: datetime | None


class OrderSummary(BaseModel):
    order_code: str
    customer_code: str
    order_date: date
    status: str
    total_cents: int
    shipping_address: str | None
    carrier: str | None
    tracking_number: str | None
    shipped_at: datetime | None
    estimated_delivery_date: date | None


class CustomerSummary(BaseModel):
    customer_code: str
    full_name: str
    email: str
    phone: str | None


class ProductSummary(BaseModel):
    sku: str
    name: str
    category: str | None
    price_cents: int
    warranty_months: int


class ProductPolicy(BaseModel):
    sku: str
    name: str
    category: str | None
    price_cents: int
    warranty_months: int
    coverage: dict
    service: dict
