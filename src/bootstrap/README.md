# bootstrap

Standalone script for setting up local Postgres data for it-man. It isn't
part of the `it_man` package -- it's a one-off tool you run against your dev
database, not something the app imports at runtime.

## What it does

1. Connects to Postgres (via `DATABASE_URL`, or the `POSTGRES_*` env vars).
2. Creates the `customers`, `products`, `orders`, `order_items`, and
   `refund_requests` tables if they don't already exist.
3. Loads the curated data in `data/*.json` and inserts it into the first
   four tables. `refund_requests` starts empty -- it's populated at
   runtime when the Refund agent submits a request for human approval.

This gives the customer-support agents' shared commerce tools
(`get_customer_details`, `get_order_details`, `get_order_items`) real rows
to query instead of an empty database -- a small fictional outdoor-gear
store ("Northbound Supply Co.") with 18 customers, 16 products across a
few categories with varied prices/warranty periods, and 24 orders spanning
different dates and statuses (placed, shipped, delivered, cancelled), so
triage scenarios -- refunds, warranty claims, shipping issues, order
changes -- have real, varied data to reason against (some orders are past
their warranty window, some are still shippable/cancellable, one is
already cancelled).

## Run it

```bash
docker compose up -d              # start Postgres (from the project root)
uv run python src/bootstrap/seed.py
```

It's idempotent: if `customers` already has rows, it skips seeding instead
of duplicating data.

## Changing the data

Edit `data/customers.json`, `data/products.json`, `data/orders.json`, or
`data/order_items.json` directly, then re-run against a fresh database
(`docker compose down -v && docker compose up -d`) to reseed.
