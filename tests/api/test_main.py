"""Tests for the FastAPI layer's auth: admin-key gating on the refund-request
endpoints, and HMAC session-token gating on /refund/chat. Uses a tiny real
(non-LLM) LangGraph graph compiled with InMemorySaver in place of the real
build_refund_agent(), so these exercise real checkpoint/get_state()
semantics without an Anthropic key or Postgres."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from cora.api import main
from cora.api.main import _compute_session_token, app
from cora.config import get_settings

client = TestClient(app)


def _make_fake_refund_agent():
    def echo(state):
        return {"refund_result": "ok"}

    builder = StateGraph(dict)
    builder.add_node("echo", echo)
    builder.set_entry_point("echo")
    builder.add_edge("echo", END)
    return builder.compile(checkpointer=InMemorySaver())


def test_refund_requests_rejects_missing_key(monkeypatch):
    monkeypatch.setattr(main, "CommerceRepository", MagicMock())
    response = client.get("/refund-requests")
    assert response.status_code == 401


def test_refund_requests_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(main, "CommerceRepository", MagicMock())
    response = client.get("/refund-requests", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_refund_requests_accepts_correct_key(monkeypatch):
    fake_repo = MagicMock()
    fake_repo.list_refund_requests.return_value = []
    monkeypatch.setattr(main, "CommerceRepository", lambda: fake_repo)
    settings = get_settings()

    response = client.get("/refund-requests", headers={"X-API-Key": settings.admin_api_key})

    assert response.status_code == 200
    assert response.json() == []


def test_refund_chat_new_session_needs_no_token_and_gets_one_back(monkeypatch):
    monkeypatch.setattr(main, "_get_refund_agent", lambda: _make_fake_refund_agent())

    response = client.post("/refund/chat", json={"session_id": "sess-new", "message": "hi"})

    assert response.status_code == 200
    assert response.json()["session_token"] == _compute_session_token("sess-new")


def test_refund_chat_existing_session_rejects_missing_or_wrong_token(monkeypatch):
    fake_agent = _make_fake_refund_agent()
    monkeypatch.setattr(main, "_get_refund_agent", lambda: fake_agent)

    # First call claims the session (no token needed yet).
    client.post("/refund/chat", json={"session_id": "sess-hijack", "message": "hi"})

    # A second caller who merely knows the session_id, with no token:
    response = client.post("/refund/chat", json={"session_id": "sess-hijack", "message": "gimme a refund"})
    assert response.status_code == 403

    # ...or a made-up token:
    response = client.post(
        "/refund/chat",
        json={"session_id": "sess-hijack", "message": "hi", "session_token": "not-the-real-token"},
    )
    assert response.status_code == 403


def test_refund_chat_legitimate_second_call_with_correct_token_succeeds(monkeypatch):
    fake_agent = _make_fake_refund_agent()
    monkeypatch.setattr(main, "_get_refund_agent", lambda: fake_agent)

    first = client.post("/refund/chat", json={"session_id": "sess-legit", "message": "hi"})
    token = first.json()["session_token"]

    second = client.post(
        "/refund/chat",
        json={"session_id": "sess-legit", "message": "again", "session_token": token},
    )

    assert second.status_code == 200
    assert second.json()["session_token"] == token
