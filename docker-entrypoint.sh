#!/usr/bin/env bash
# Runs both the FastAPI backend and the Streamlit UI in one container, for
# Render's single-combined-service deployment. Only the UI binds Render's
# public $PORT; the API stays on an internal-only loopback port ($API_PORT)
# that only the UI process (via API_URL) ever talks to.
set -euo pipefail

# Idempotent: creates tables on a fresh DB, skips re-seeding an already
# populated one, but still backfills any newly added catalog entries/
# shipments -- see src/bootstrap/seed.py.
uv run python src/bootstrap/seed.py

uv run uvicorn cora.api.main:app --host 0.0.0.0 --port "${API_PORT:-8000}" &
api_pid=$!

uv run streamlit run src/cora/ui/app.py \
  --server.port "${PORT:-8501}" \
  --server.address 0.0.0.0 \
  --server.headless true &
ui_pid=$!

# Exit (and let Render restart the container) the instant either process
# dies, instead of limping along with one half silently down.
wait -n "$api_pid" "$ui_pid"
exit $?
