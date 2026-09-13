"""Bootstraps the Postgres database for CORA.

Creates the `customers`, `products`, `shipments`, `orders`, `order_items`,
and `refund_requests` tables (if they don't already exist) and fills the
first two plus `shipments`/`orders`/`order_items` with curated synthetic
data loaded from `data/*.json` (a fictional outdoor-gear store, "Northbound
Supply Co."), so the customer-support agents' tools have real
orders/products/customers to query. `refund_requests` starts empty -- it's
populated at runtime when the Refund agent submits a request for human
approval.

Run with: `uv run python src/bootstrap/seed.py`
(Start Postgres first: `docker compose up -d`)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"

DDL = """
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    customer_code TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    price_cents INTEGER NOT NULL,
    warranty_months INTEGER NOT NULL DEFAULT 0
);

-- One row per shipment (carrier/tracking/dates) -- created once an order
-- actually ships. Kept as its own table, not columns on `orders`, since
-- an order has no shipment at all until then; `orders.shipment_id` is
-- null up to that point rather than a row of all-null shipping columns.
CREATE TABLE IF NOT EXISTS shipments (
    id SERIAL PRIMARY KEY,
    carrier TEXT NOT NULL,
    tracking_number TEXT NOT NULL,
    shipped_at TIMESTAMPTZ NOT NULL,
    estimated_delivery_date DATE
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_code TEXT UNIQUE NOT NULL,
    customer_code TEXT NOT NULL REFERENCES customers(customer_code),
    order_date DATE NOT NULL,
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL DEFAULT 0,
    shipping_address TEXT,
    shipment_id INTEGER REFERENCES shipments(id)
);

-- ALTER (not just the inline column above) so a database whose `orders`
-- table already existed before `shipment_id` was introduced still picks
-- it up -- CREATE TABLE IF NOT EXISTS is a no-op against an existing
-- table, so a live database wouldn't otherwise gain the column at all.
ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipment_id INTEGER REFERENCES shipments(id);

CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_code TEXT NOT NULL REFERENCES orders(order_code),
    sku TEXT NOT NULL REFERENCES products(sku),
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS refund_requests (
    id SERIAL PRIMARY KEY,
    order_code TEXT NOT NULL REFERENCES orders(order_code),
    amount_cents INTEGER NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);
"""


def load_data(name: str) -> list[dict]:
    with (DATA_DIR / name).open() as f:
        return json.load(f)


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL") or (
        "postgresql://{user}:{password}@{host}:{port}/{db}".format(
            user=os.environ.get("POSTGRES_USER", "cora"),
            password=os.environ.get("POSTGRES_PASSWORD", "cora"),
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            db=os.environ.get("POSTGRES_DB", "cora"),
        )
    )


def create_tables(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()


def already_seeded(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM customers")
        (count,) = cur.fetchone()
    return count > 0


def shipments_seeded(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM shipments")
        (count,) = cur.fetchone()
    return count > 0


def seed_customers(conn: psycopg.Connection, customers: list[dict]) -> None:
    with conn.cursor() as cur:
        for customer in customers:
            cur.execute(
                "INSERT INTO customers (customer_code, full_name, email, phone) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (customer_code) DO NOTHING",
                (
                    customer["customer_code"],
                    customer["full_name"],
                    customer["email"],
                    customer["phone"],
                ),
            )
    conn.commit()


def seed_products(conn: psycopg.Connection, products: list[dict]) -> None:
    with conn.cursor() as cur:
        for product in products:
            cur.execute(
                "INSERT INTO products (sku, name, category, price_cents, warranty_months) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (sku) DO NOTHING",
                (
                    product["sku"],
                    product["name"],
                    product["category"],
                    product["price_cents"],
                    product["warranty_months"],
                ),
            )
    conn.commit()


def seed_orders(conn: psycopg.Connection, orders: list[dict]) -> None:
    with conn.cursor() as cur:
        for order in orders:
            cur.execute(
                "INSERT INTO orders (order_code, customer_code, order_date, status, shipping_address) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (order_code) DO NOTHING",
                (
                    order["order_code"],
                    order["customer_code"],
                    order["order_date"],
                    order["status"],
                    order["shipping_address"],
                ),
            )
    conn.commit()


def seed_shipments(conn: psycopg.Connection, shipments: list[dict]) -> None:
    """Insert each shipment and link it back to its order.

    Requires `seed_orders` to have already run -- each entry references its
    order by `order_code`, same convention as `order_items.json`. Only
    orders that have actually shipped appear here at all; every other
    order keeps `shipment_id` NULL.
    """
    with conn.cursor() as cur:
        for shipment in shipments:
            cur.execute(
                "INSERT INTO shipments (carrier, tracking_number, shipped_at, estimated_delivery_date) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (
                    shipment["carrier"],
                    shipment["tracking_number"],
                    shipment["shipped_at"],
                    shipment["estimated_delivery_date"],
                ),
            )
            (shipment_id,) = cur.fetchone()
            cur.execute(
                "UPDATE orders SET shipment_id = %s WHERE order_code = %s",
                (shipment_id, shipment["order_code"]),
            )
    conn.commit()


def seed_order_items(conn: psycopg.Connection, products_by_sku: dict[str, dict], items: list[dict]) -> None:
    with conn.cursor() as cur:
        for item in items:
            cur.execute(
                "INSERT INTO order_items (order_code, sku, product_name, quantity, unit_price_cents) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    item["order_code"],
                    item["sku"],
                    products_by_sku[item["sku"]]["name"],
                    item["quantity"],
                    item["unit_price_cents"],
                ),
            )
        # Backfill each order's total from its line items now that they exist.
        cur.execute(
            "UPDATE orders SET total_cents = sub.total "
            "FROM (SELECT order_code, SUM(quantity * unit_price_cents) AS total "
            "      FROM order_items GROUP BY order_code) AS sub "
            "WHERE orders.order_code = sub.order_code"
        )
    conn.commit()


def main() -> None:
    with psycopg.connect(get_database_url()) as conn:
        create_tables(conn)

        if already_seeded(conn):
            print("Database already has customers -- skipping seed.")
            # New catalog entries added to products.json after the initial
            # seed still need to land in an already-seeded database --
            # seed_products is idempotent (ON CONFLICT DO NOTHING on sku),
            # so it's safe to re-run against existing data.
            products = load_data("products.json")
            seed_products(conn, products)
            # `shipments` was added after some databases were already
            # seeded -- backfill it on its own rather than requiring a
            # full reseed, without touching any existing data (including
            # anything created at runtime, like refund_requests).
            if not shipments_seeded(conn):
                shipments = load_data("shipments.json")
                seed_shipments(conn, shipments)
                print(f"Backfilled {len(shipments)} shipments.")
            return

        customers = load_data("customers.json")
        products = load_data("products.json")
        orders = load_data("orders.json")
        order_items = load_data("order_items.json")
        shipments = load_data("shipments.json")
        products_by_sku = {p["sku"]: p for p in products}

        seed_customers(conn, customers)
        seed_products(conn, products)
        seed_orders(conn, orders)
        seed_order_items(conn, products_by_sku, order_items)
        seed_shipments(conn, shipments)

        print(
            f"Seeded {len(customers)} customers, {len(products)} products, "
            f"{len(orders)} orders, {len(order_items)} order line items, "
            f"and {len(shipments)} shipments."
        )


if __name__ == "__main__":
    main()
