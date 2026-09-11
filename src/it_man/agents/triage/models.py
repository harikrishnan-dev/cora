from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class InfoGatheringDecision(BaseModel):
    info_complete: bool
    clarifying_question: str | None = None


class ClassificationDecision(BaseModel):
    category: Literal["refund", "warranty_service", "shipping_delivery", "order_change"]
    urgency: Literal["low", "medium", "high", "critical"]
