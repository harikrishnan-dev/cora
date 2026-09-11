from __future__ import annotations

from langchain_core.tools import tool

from cora.repository.commerce_repository import CommerceRepository


def make_shipping_delivery_tools(commerce_repository: CommerceRepository) -> list:
    @tool
    def get_shipping_status(order_code: str) -> dict:
        """Look up the shipping status of an order."""
        order = commerce_repository.get_order(order_code)
        if not order:
            return {"error": f"No order found with code {order_code}"}
        return {
            "order_code": order_code,
            "status": order["status"],
            "shipping_address": order["shipping_address"],
        }

    @tool
    def initiate_reshipment(order_code: str, reason: str) -> dict:
        """Trigger a reshipment for a lost, damaged, or misdelivered order.

        STUB: logs and returns a fake confirmation; no real shipping/carrier
        system is wired up yet. Not gated by human approval -- per policy,
        approval is reserved for actions that delete records or refund
        money, and a reshipment is neither.
        """
        reshipment = {"status": "reshipment_initiated", "order_code": order_code, "reason": reason}
        print(f"[stub] reshipment initiated: {reshipment}")
        return reshipment

    return [get_shipping_status, initiate_reshipment]
