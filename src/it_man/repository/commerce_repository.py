"""Abstraction the app depends on for customer/order/refund data.

Callers (e.g. agents/common/commerce_tools.py, api/main.py) go through
this, not through a specific store, so the underlying data source can
change without touching the agents or the API.
"""

from __future__ import annotations

from it_man.store.postgres_store import PostgresStore


class CommerceRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self._store = store or PostgresStore()

    def get_customer(self, customer_code: str) -> dict | None:
        return self._store.fetch_one(
            "SELECT customer_code, full_name, email, phone "
            "FROM customers WHERE customer_code = %s",
            (customer_code,),
        )

    def get_order(self, order_code: str) -> dict | None:
        return self._store.fetch_one(
            "SELECT order_code, customer_code, order_date, status, total_cents, shipping_address "
            "FROM orders WHERE order_code = %s",
            (order_code,),
        )

    def get_order_items(self, order_code: str) -> list[dict]:
        return self._store.fetch_all(
            "SELECT sku, product_name, quantity, unit_price_cents "
            "FROM order_items WHERE order_code = %s ORDER BY id",
            (order_code,),
        )

    def get_product(self, sku: str) -> dict | None:
        return self._store.fetch_one(
            "SELECT sku, name, category, price_cents, warranty_months "
            "FROM products WHERE sku = %s",
            (sku,),
        )

    def set_order_status(self, order_code: str, status: str) -> dict | None:
        return self._store.fetch_one(
            "UPDATE orders SET status = %s WHERE order_code = %s "
            "RETURNING order_code, customer_code, order_date, status, total_cents, shipping_address",
            (status, order_code),
        )

    def create_refund_request(self, order_code: str, amount_cents: int, reason: str) -> dict:
        return self._store.fetch_one(
            "INSERT INTO refund_requests (order_code, amount_cents, reason) "
            "VALUES (%s, %s, %s) "
            "RETURNING id, order_code, amount_cents, reason, status, requested_at",
            (order_code, amount_cents, reason),
        )

    def list_refund_requests(self, status: str | None = None) -> list[dict]:
        if status is None:
            return self._store.fetch_all(
                "SELECT id, order_code, amount_cents, reason, status, requested_at, resolved_at "
                "FROM refund_requests ORDER BY requested_at DESC"
            )
        return self._store.fetch_all(
            "SELECT id, order_code, amount_cents, reason, status, requested_at, resolved_at "
            "FROM refund_requests WHERE status = %s ORDER BY requested_at DESC",
            (status,),
        )

    def set_refund_request_status(self, request_id: int, status: str) -> dict | None:
        return self._store.fetch_one(
            "UPDATE refund_requests SET status = %s, resolved_at = now() "
            "WHERE id = %s "
            "RETURNING id, order_code, amount_cents, reason, status, requested_at, resolved_at",
            (status, request_id),
        )
