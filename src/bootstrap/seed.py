"""Bootstraps the Postgres database for it-man.

Creates the `customers`, `products`, `orders`, `order_items`, and
`refund_requests` tables (if they don't already exist) and fills the first
four with curated synthetic data loaded from `data/*.json` (a fictional
outdoor-gear store, "Northbound Supply Co."), so the customer-support
agents' tools have real orders/products/customers to query.
`refund_requests` starts empty -- it's populated at runtime when the Refund
agent submits a request for human approval.

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

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_code TEXT UNIQUE NOT NULL,
    customer_code TEXT NOT NULL REFERENCES customers(customer_code),
    order_date DATE NOT NULL,
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL DEFAULT 0,
    shipping_address TEXT
);

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
            user=os.environ.get("POSTGRES_USER", "it_man"),
            password=os.environ.get("POSTGRES_PASSWORD", "it_man"),
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            db=os.environ.get("POSTGRES_DB", "it_man"),
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
            return

        customers = load_data("customers.json")
        products = load_data("products.json")
        orders = load_data("orders.json")
        order_items = load_data("order_items.json")
        products_by_sku = {p["sku"]: p for p in products}

        seed_customers(conn, customers)
        seed_products(conn, products)
        seed_orders(conn, orders)
        seed_order_items(conn, products_by_sku, order_items)

        print(
            f"Seeded {len(customers)} customers, {len(products)} products, "
            f"{len(orders)} orders, and {len(order_items)} order line items."
        )


if __name__ == "__main__":
    main()
