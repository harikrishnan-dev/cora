from __future__ import annotations

from typing import Annotated

from langchain.tools import InjectedState
from langchain_core.tools import tool

from cora.agents.refund.catalog import get_refund_policy as lookup_refund_policy
from cora.repository.commerce_repository import CommerceRepository


def make_refund_tools(commerce_repository: CommerceRepository) -> list:
    @tool
    def get_refund_policy(
        product_id: Annotated[str | None, InjectedState("product_id")] = None,
    ) -> dict:
        """Look up this store's refund policy for the product this conversation
        is about: the return window, restocking fee, and condition the item
        must be in to qualify. The product is identified automatically from
        the conversation -- this tool takes no arguments.
        """
        if not product_id:
            return {"error": "No product could be identified for this conversation."}
        policy = lookup_refund_policy(product_id)
        return policy or {"error": f"No refund policy found for product {product_id}"}

    @tool
    def is_already_refunded_or_not(order_code: str) -> dict:
        """Check whether a refund has already been approved, or is still
        pending approval, for an order.

        Args:
            order_code: The order to check.
        """
        requests = commerce_repository.get_refund_requests_for_order(order_code)
        return {
            "order_code": order_code,
            "already_refunded": any(r["status"] == "approved" for r in requests),
            "has_pending_request": any(r["status"] == "pending" for r in requests),
            "requests": requests,
        }

    @tool
    def initiate_refund(order_code: str, amount_cents: int, reason: str) -> dict:
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

    return [get_refund_policy, is_already_refunded_or_not, initiate_refund]
