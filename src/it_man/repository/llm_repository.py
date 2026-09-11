"""Abstraction the app depends on for LLM calls.

Callers (e.g. agents/*/agent.py) go through this, not through a specific
store, so the underlying provider can change without touching the graphs.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from it_man.store.anthropic_store import AnthropicStore


class LLMRepository:
    def __init__(self, store: AnthropicStore | None = None) -> None:
        self._store = store or AnthropicStore()

    def invoke(self, messages: list[BaseMessage]) -> str:
        return self._store.invoke(messages)

    def get_model(self) -> BaseChatModel:
        return self._store.get_model()

    def as_text(self, content: str | list) -> str:
        return self._store.as_text(content)
