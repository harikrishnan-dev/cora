from __future__ import annotations

from datetime import UTC, date, datetime

from langchain_core.tools import tool

from it_man.repository.commerce_repository import CommerceRepository


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, 28)  # keep it simple, avoid month-length edge cases
    return date(year, month, day)


def make_warranty_service_tools(commerce_repository: CommerceRepository) -> list:
    @tool
    def check_warranty_eligibility(order_code: str, sku: str) -> dict:
        """Check whether a product purchased on an order is still under warranty.

        Args:
            order_code: The order the product was purchased on.
            sku: The product's SKU.
        """
        order = commerce_repository.get_order(order_code)
        if not order:
            return {"error": f"No order found with code {order_code}"}
        product = commerce_repository.get_product(sku)
        if not product:
            return {"error": f"No product found with sku {sku}"}
        expires_on = _add_months(order["order_date"], product["warranty_months"])
        return {
            "order_code": order_code,
            "sku": sku,
            "warranty_months": product["warranty_months"],
            "expires_on": expires_on.isoformat(),
            "eligible": datetime.now(UTC).date() <= expires_on,
        }

    @tool
    def create_service_ticket(order_code: str, sku: str, issue_description: str) -> dict:
        """Log a service/repair ticket for a defective product.

        STUB: logs and returns a fake confirmation; no real ticketing system
        is wired up yet.
        """
        ticket = {
            "status": "logged",
            "order_code": order_code,
            "sku": sku,
            "issue_description": issue_description,
        }
        print(f"[stub] service ticket created: {ticket}")
        return ticket

    return [check_warranty_eligibility, create_service_ticket]
