from __future__ import annotations

from datetime import UTC, date, datetime

from langchain_core.tools import tool

from cora.agents.refund.catalog import get_refund_policy as lookup_return_policy
from cora.agents.warranty_service.catalog import (
    decide_resolution,
    estimate_repair_cost_cents,
    get_coverage_policy,
)
from cora.repository.commerce_repository import CommerceRepository


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
    def get_warranty_coverage_policy(sku: str) -> dict:
        """Look up what this store's warranty actually covers and excludes
        for a product's category. A product can be within its warranty
        window (per check_warranty_eligibility) and still not qualify, if
        the cause of the defect is one of the excluded causes -- e.g.
        accidental damage isn't covered just because the clock hasn't run
        out.

        Args:
            sku: The product's SKU.
        """
        product = commerce_repository.get_product(sku)
        if not product:
            return {"error": f"No product found with sku {sku}"}
        policy = get_coverage_policy(product["category"])
        return {"sku": sku, "category": product["category"], **policy}

    @tool
    def check_return_policy(sku: str) -> dict:
        """Check whether a product can be returned for a refund at all when
        there's NO defect -- this store's return window and any final-sale
        restriction. Use this for a plain refund request with no defect
        claim, before deciding whether to route it to Refund; the refund
        specialist will still verify the order's return window and item
        condition itself.

        Args:
            sku: The product's SKU.
        """
        policy = lookup_return_policy(sku)
        return policy or {"error": f"No return policy found for sku {sku}"}

    @tool
    def decide_repair_vs_replace(sku: str) -> dict:
        """For a GENUINE, covered defect, decide how it should be resolved:
        "repair", "replace", or "refund" -- some categories aren't
        practical to service in-house even for a real defect, in which case
        this returns "refund" and the customer should be routed to Refund
        instead of getting a service ticket.

        Args:
            sku: The product's SKU.
        """
        product = commerce_repository.get_product(sku)
        if not product:
            return {"error": f"No product found with sku {sku}"}
        resolution = decide_resolution(product["category"], product["price_cents"])
        return {"sku": sku, "category": product["category"], "resolution": resolution}

    @tool
    def estimate_repair_cost(sku: str) -> dict:
        """Quote the cost of a paid, out-of-warranty repair for a product --
        use this when check_warranty_eligibility says the product is no
        longer covered, to offer the customer a paid alternative instead of
        an outright refusal.

        Args:
            sku: The product's SKU.
        """
        product = commerce_repository.get_product(sku)
        if not product:
            return {"error": f"No product found with sku {sku}"}
        cost_cents = estimate_repair_cost_cents(product["category"], product["price_cents"])
        return {
            "sku": sku,
            "price_cents": product["price_cents"],
            "estimated_repair_cost_cents": cost_cents,
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

    return [
        check_warranty_eligibility,
        get_warranty_coverage_policy,
        check_return_policy,
        decide_repair_vs_replace,
        estimate_repair_cost,
        create_service_ticket,
    ]
