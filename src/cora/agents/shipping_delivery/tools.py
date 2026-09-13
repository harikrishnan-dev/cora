from __future__ import annotations

from langchain_core.tools import tool

from cora.repository.commerce_repository import CommerceRepository

# Orders move placed -> shipped -> delivered (or placed -> cancelled). Only
# "placed" means nothing has left the warehouse yet -- once it's "shipped"
# or "delivered" the shipping address can no longer be changed, and a
# "cancelled" order isn't going anywhere at all.
ADDRESS_EDITABLE_STATUSES = {"placed"}


def make_shipping_tools(commerce_repository: CommerceRepository) -> list:
    @tool
    def update_shipping_address(order_code: str, new_address: str) -> dict:
        """Update the shipping address for an order.

        Only works while the order hasn't been packed/shipped yet (status
        'placed'). Always check the return value -- if `updated` is False,
        the order has already shipped (or was cancelled) and the address
        cannot be changed; tell the customer instead of assuming it worked.

        Args:
            order_code: The order to update.
            new_address: The full new shipping address.
        """
        order = commerce_repository.get_order(order_code)
        if not order:
            return {"error": f"No order found with code {order_code}"}

        if order["status"] not in ADDRESS_EDITABLE_STATUSES:
            reason = (
                "This order was cancelled, so there's no shipment to update."
                if order["status"] == "cancelled"
                else f"Order is already '{order['status']}' -- it has already been dispatched."
            )
            return {
                "updated": False,
                "order_code": order_code,
                "status": order["status"],
                "reason": reason,
            }

        updated = commerce_repository.update_shipping_address(order_code, new_address)
        return {"updated": True, **updated}

    return [update_shipping_address]
