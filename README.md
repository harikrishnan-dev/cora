# CORA

**CORA** — **C**ustomer **O**perations & **R**esolution **A**gent — is a
multi-agent customer support app for e-commerce, built with **LangGraph**,
**FastAPI**, **Streamlit**, and **uv**. A customer chats with the system;
Triage figures out what they need and routes to a specialist team.

## Architecture

![Architecture](Architecture.png)

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
