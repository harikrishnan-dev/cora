# it-man

A multi-agent customer support app for e-commerce, built with **LangGraph**,
**FastAPI**, **Streamlit**, and **uv**. A customer chats with the system;
Triage figures out what they need and routes to a specialist team.

## Architecture

- `src/it_man/agents/graph.py` — the top-level graph: `gather_info` (asks one
  clarifying question until enough detail has been collected) → `classify`
  (structured-output classification into one of 4 categories) → one of 4
  specialist agents → `END`.
- `src/it_man/agents/triage/` — `gather_info` and `classify`, both pure
  structured-output steps (no tool-calling).
- `src/it_man/agents/{refund,warranty_service,shipping_delivery,order_changes}/`
  — the 4 specialist agents, each a tool-calling `create_agent` bound to the
  shared commerce-lookup tools plus its own domain tools:
  - **Refund** — `request_refund` submits a request for human approval; it
    never processes a refund directly.
  - **Warranty & Service** — `check_warranty_eligibility`, `create_service_ticket`.
  - **Shipping & Delivery** — `get_shipping_status`, `initiate_reshipment`.
  - **Order Changes & Cancellation** — `check_order_editable`, `cancel_order`.
- `src/it_man/agents/common/commerce_tools.py` — `get_customer_details`,
  `get_order_details`, `get_order_items`, shared by all 4 specialists.
- `src/it_man/store/` — thin wrappers around external clients (`AnthropicStore` for
  `langchain_anthropic`, `PostgresStore` for `psycopg`). Nothing outside `store/` should
  import those client libraries directly.
- `src/it_man/repository/` — the app-facing abstractions everything else depends on
  (`LLMRepository`, `CommerceRepository`), each wrapping a store. Agents/tools take a
  repository as a constructor parameter (dependency injection), so tests can pass in a
  fake one and `build_graph` is the single place that decides which repository each
  node uses.
- `src/it_man/api/` — FastAPI service. `/chat` is wired to the real graph. `GET
  /refund-requests`, `POST /refund-requests/{id}/approve`, `POST
  /refund-requests/{id}/reject` back the human-approval flow for refunds — the only
  action in this app gated by human approval, per policy (approval is reserved for
  actions that delete records or refund money).
- `src/it_man/ui/app.py` — Streamlit multipage entry point with two pages:
  - **Chat** (`views/chat.py`) — sends the full conversation to `/chat` and
    renders the reply, including mid-conversation clarifying questions.
  - **Pending Requests** (`views/pending_requests.py`) — lists pending refund
    requests from the API with Approve/Reject actions.
- `src/it_man/config.py` — settings loaded from environment / `.env`.
- `src/bootstrap/` — standalone script (not part of the `it_man` package) that creates
  the Postgres tables (`customers`, `products`, `orders`, `order_items`,
  `refund_requests`) and loads the first four with curated synthetic data from
  `data/*.json` (a fictional outdoor-gear store, "Northbound Supply Co.", with 18
  customers, 16 products, and 24 orders spanning different dates/statuses).
  `refund_requests` starts empty -- populated at runtime. `seed.py` is idempotent
  (skips if `customers` is already populated).

## Setup

```bash
cp .env.example .env   # then set ANTHROPIC_API_KEY
uv sync
```

### LangSmith tracing (optional)

Set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and (optionally)
`LANGSMITH_PROJECT` in `.env` to trace every graph run in the LangSmith UI.
`config.get_settings()` mirrors these into the process environment (the
`langsmith` SDK reads env vars directly, not this app's `Settings` object),
so it's enough to just set them in `.env` -- no other wiring needed.

## Postgres

```bash
docker compose up -d              # starts Postgres on localhost:5432
uv run python src/bootstrap/seed.py   # creates tables + synthetic customers/products/orders
```

## Run the API

```bash
uv run uvicorn it_man.api.main:app --reload --port 8000
```

## Run the Streamlit UI

In a second terminal (with the API running):

```bash
uv run streamlit run src/it_man/ui/app.py
```

## Tests

```bash
uv run pytest
```

## Lint

```bash
uv run ruff check .
```
