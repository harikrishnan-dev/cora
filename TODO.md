# Production-readiness TODO

- [ ] **Fix session/thread auth hole** — `session_id` from the client is used
      directly as the LangGraph `thread_id` with no ownership check
      (`src/cora/api/main.py:50`, `:86`), so any caller can resume another
      session's paused conversation. The refund approve/reject endpoints
      (`src/cora/api/main.py:106-121`) also have no auth at all.

- [ ] **Swap `InMemorySaver` for a Postgres checkpointer** — both the main
      graph (`src/cora/agents/graph.py`) and the refund agent
      (`src/cora/api/main.py:29`) use `InMemorySaver`, so a restart drops
      every in-flight/paused conversation, even though `psycopg` is already
      a dependency.

- [x] **Finish `warranty_service`** — added `models.py` and the
      interrupt-based `ClarifyingQuestion`/`FinalAnswer` loop matching
      `refund`/`shipping_delivery`, registered it in `graph.py`'s
      `_IMPLEMENTED_SPECIALISTS`, and added `decide_repair_vs_replace`/
      `estimate_repair_cost` tools. `order_changes` (and the `order_change`
      triage category) was dropped entirely rather than finished.

- [ ] **Add CI** — no `.github/workflows` exist; add one running `pytest`
      and `ruff` on push/PR.

- [ ] **Wire up one real third-party integration** — e.g. replace
      `warranty_service`'s stubbed `create_service_ticket` (currently just
      logs and fakes a confirmation) with a real ticketing call, or add
      Slack notifications for the refund approval queue instead of relying
      on manually polling the Streamlit admin panel.

- [ ] **Add a small eval set for the triage classifier** — e.g. 20-30
      labeled sample tickets checked against expected `category`/`urgency`,
      to catch prompt regressions instead of relying on routing/wiring
      tests alone.
