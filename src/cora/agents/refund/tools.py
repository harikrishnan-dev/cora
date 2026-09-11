from __future__ import annotations

from langchain_core.tools import tool

from cora.repository.commerce_repository import CommerceRepository


def make_refund_tools(commerce_repository: CommerceRepository) -> list:
    @tool
    def request_refund(order_code: str, amount_cents: int, reason: str) -> dict:
        """Submit a refund request for human approval.

        This does NOT process the refund immediately -- it creates a pending
        request that a human must approve before any money moves. No refund
        is ever issued directly by this tool.

        Args:
            order_code: The order the refund applies to.
            amount_cents: The amount to refund, in cents.
            reason: Why the customer is requesting a refund.
        """
        return commerce_repository.create_refund_request(order_code, amount_cents, reason)

    return [request_refund]
