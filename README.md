# CORA

**CORA** — **C**ustomer **O**perations & **R**esolution **A**gent — is a
multi-agent customer support app for e-commerce, built with **LangGraph**,
**FastAPI**, **Streamlit**, and **uv**. A customer chats with the system;
Triage figures out what they need and routes to a specialist team.

## Architecture

- `src/cora/agents/graph.py` — the top-level graph: `gather_info` (asks one
  clarifying question until enough detail has been collected) → `classify`
  (structured-output classification into `shipping_delivery` or
  `warranty_service` — `refund` is not a classify-time destination) → the
  matching specialist → `END`. `warranty_service` is the front door for
  anything that isn't a shipping issue — a defect claim, or a plain refund
  request with no defect — and decides for itself whether to resolve the
  case or hand it off to `refund` (`route_after_warranty_service`); `refund`
  is otherwise only reachable via the standalone `/refund/chat` endpoint.
- `src/cora/agents/triage/` — `gather_info` and `classify`, both pure
  structured-output steps (no tool-calling).
- `src/cora/agents/{refund,warranty_service,shipping_delivery}/` — the 3
  specialist agents, each a tool-calling `create_agent` bound to the shared
  commerce-lookup tools plus its own domain tools, wrapped in a `decide` <->
  `ask_human` graph that pauses via `interrupt()` to ask the customer a
  clarifying question when needed:
  - **Refund** — `get_refund_policy`, `is_already_refunded_or_not`,
    `initiate_refund` submits a request for human approval; it never
    processes a refund directly.
  - **Warranty & Service** — `check_warranty_eligibility`,
    `get_warranty_coverage_policy`, `check_return_policy`,
    `decide_repair_vs_replace`, `estimate_repair_cost`,
    `create_service_ticket`. `ForwardToRefund` hands the ticket to Refund,
    but only for a genuine covered defect whose category isn't practical to
    service in-house, or a no-defect refund request with a valid return
    policy -- an ineligible or customer-caused claim is denied outright,
    never forwarded.
  - **Shipping & Delivery** — `update_shipping_address`.
- `src/cora/agents/common/commerce_tools.py` — `get_customer_details`,
  `get_order_details`, `get_order_items`, `get_product_details`, shared by
  all 3 specialists.
- `src/cora/store/` — thin wrappers around external clients (`AnthropicStore` for
  `langchain_anthropic`, `PostgresStore` for `psycopg`). Nothing outside `store/` should
  import those client libraries directly.
- `src/cora/repository/` — the app-facing abstractions everything else depends on
  (`LLMRepository`, `CommerceRepository`), each wrapping a store. Agents/tools take a
  repository as a constructor parameter (dependency injection), so tests can pass in a
  fake one and `build_graph` is the single place that decides which repository each
  node uses.
- `src/cora/api/` — FastAPI service. `/chat` is wired to the real graph, keyed by a
  `session_id` (LangGraph checkpointer-backed, so only the latest message needs to be
  sent each turn). `GET /refund-requests`, `POST /refund-requests/{id}/approve`, `POST
  /refund-requests/{id}/reject` back the human-approval flow for refunds — the only
  action in this app gated by human approval, per policy (approval is reserved for
  actions that delete records or refund money).
- `src/cora/ui/app.py` — Streamlit multipage entry point:
  - **Chat** (`views/chat.py`) — sends the latest message to `/chat` and
    renders the reply, including mid-conversation clarifying questions.
  - **Pending Requests** (`views/pending_requests.py`) — lists pending refund
    requests from the API with Approve/Reject actions.
  - **Orders** (`views/orders.py`) — every order in the store, with shipment
    status/carrier/tracking where available.
  - **Policies** (`views/policies.py`) — pick a product, see its warranty
    coverage and repair/replace/refund policy.
  - **Customers** (`views/customers.py`) — every registered customer.
- `src/cora/config.py` — settings loaded from environment / `.env`.
- `src/bootstrap/` — standalone script (not part of the `cora` package) that creates
  the Postgres tables (`customers`, `products`, `shipments`, `orders`, `order_items`,
  `refund_requests`) and loads the first five with curated synthetic data from
  `data/*.json` (a fictional outdoor-gear store, "Northbound Supply Co.", with 18
  customers, 28 products, and 24 orders spanning different dates/statuses).
  `refund_requests` starts empty -- populated at runtime. `seed.py` is idempotent
  (skips full seeding if `customers` is already populated, but always re-runs the
  product seed and backfills `shipments` so new catalog entries still land).

## Running the project

### 1. Configure environment

```bash
cp .env.example .env   # then set ANTHROPIC_API_KEY
uv sync
```

**LangSmith tracing (optional):** set `LANGSMITH_TRACING=true`,
`LANGSMITH_API_KEY`, and (optionally) `LANGSMITH_PROJECT` in `.env` to trace
every graph run in the LangSmith UI. `config.get_settings()` mirrors these
into the process environment (the `langsmith` SDK reads env vars directly,
not this app's `Settings` object), so setting them in `.env` is enough --
no other wiring needed.

### 2. Start Postgres and seed data

```bash
docker compose up -d              # starts Postgres on localhost:5432
uv run python src/bootstrap/seed.py   # creates tables + synthetic customers/products/orders
```

### 3. Run the API

```bash
uv run uvicorn cora.api.main:app --reload --port 8000
```

### 4. Run the Streamlit UI

In a second terminal (with the API running):

```bash
uv run streamlit run src/cora/ui/app.py
```

### Run with Docker instead

`Dockerfile` runs the API and the UI together in a single container (the
same image used to deploy to Render) — an alternative to steps 3–4 above if
you'd rather not run two `uv run` processes by hand. Still needs Postgres
from step 2.

```bash
docker compose up -d   # if not already running
docker build -t cora .
docker run --rm -p 8501:8501 \
  -e ANTHROPIC_API_KEY=<your-key> \
  -e DATABASE_URL=postgresql://cora:cora@host.docker.internal:5432/cora \
  -e ADMIN_API_KEY=dev-admin-key \
  -e SESSION_SECRET=dev-session-secret-change-me \
  cora
```

Then open http://localhost:8501. `host.docker.internal` resolves to the host
machine on Docker Desktop (Mac/Windows) out of the box; on Linux add
`--add-host=host.docker.internal:host-gateway` to the `docker run` command.
The container seeds the database itself on startup (same idempotent
`seed.py`), runs the API on an internal-only port, and exposes only the
Streamlit UI on `8501`.

### Tests and lint

```bash
uv run pytest
uv run ruff check .
```

### LangGraph Studio (optional)

`langgraph.json` points the LangGraph CLI at `build_graph()` via a zero-arg
`load_graph()` wrapper (the CLI's loader only accepts 0/1/2-parameter
factories). Requires the `langgraph-cli` dev dependency, already included:

```bash
uv run langgraph dev
```
