from __future__ import annotations

from langchain_core.tools import tool

from it_man.repository.commerce_repository import CommerceRepository

EDITABLE_STATUSES = {"placed"}


def make_order_changes_tools(commerce_repository: CommerceRepository) -> list:
    @tool
    def check_order_editable(order_code: str) -> dict:
        """Check whether an order can still be changed or cancelled (i.e. hasn't shipped yet)."""
        order = commerce_repository.get_order(order_code)
        if not order:
            return {"error": f"No order found with code {order_code}"}
        return {
            "order_code": order_code,
            "status": order["status"],
            "editable": order["status"] in EDITABLE_STATUSES,
        }

    @tool
    def cancel_order(order_code: str) -> dict:
        """Cancel an order that hasn't shipped yet.

        Only orders in the 'placed' status can be cancelled. Not gated by
        human approval -- per policy, approval is reserved for actions that
        delete records or refund money, and cancelling an unshipped order
        (a status update) is neither.
        """
        order = commerce_repository.get_order(order_code)
        if not order:
            return {"error": f"No order found with code {order_code}"}
        if order["status"] not in EDITABLE_STATUSES:
            return {
                "error": (
                    f"Order {order_code} is already '{order['status']}' "
                    "and can no longer be cancelled."
                )
            }
        return commerce_repository.set_order_status(order_code, "cancelled")

    return [check_order_editable, cancel_order]
