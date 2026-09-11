from __future__ import annotations

from langchain_core.tools import tool

from it_man.repository.commerce_repository import CommerceRepository


def make_commerce_tools(commerce_repository: CommerceRepository) -> list:
    """Build the customer/order lookup tools bound to a given `CommerceRepository`.

    Taking the repository as a parameter (rather than importing a
    module-level singleton) lets each specialist agent's `build_tools`
    decide which repository these tools use, and lets tests substitute a
    fake/stub repository. Shared across all 4 specialist agents, since each
    needs to look up the order/customer before acting on it.
    """

    @tool
    def get_customer_details(customer_code: str) -> dict:
        """Look up a customer's name, email, and phone by customer code."""
        customer = commerce_repository.get_customer(customer_code)
        return customer or {"error": f"No customer found with code {customer_code}"}

    @tool
    def get_order_details(order_code: str) -> dict:
        """Look up an order's customer, date, status, total, and shipping address by order code."""
        order = commerce_repository.get_order(order_code)
        return order or {"error": f"No order found with code {order_code}"}

    @tool
    def get_order_items(order_code: str) -> list[dict]:
        """Look up the line items (product, quantity, price) on an order."""
        return commerce_repository.get_order_items(order_code)

    @tool
    def get_product_details(sku: str) -> dict:
        """Look up a product's name, category, price, and warranty period by SKU."""
        product = commerce_repository.get_product(sku)
        return product or {"error": f"No product found with sku {sku}"}

    return [get_customer_details, get_order_details, get_order_items, get_product_details]
