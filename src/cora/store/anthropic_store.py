"""Thin wrapper around the Anthropic chat model API.

This is the only place in the project that talks to `langchain_anthropic`
directly. Anything that needs an LLM call should go through
`repository/llm_repository.py` instead of importing this module.
"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from cora.config import get_settings


class AnthropicStore:
    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self._llm = ChatAnthropic(
            model=model or settings.model_name,
            temperature=0,
            api_key=settings.anthropic_api_key,
        )

    def invoke(self, messages: list[BaseMessage]) -> str:
        response = self._llm.invoke(messages)
        return self.as_text(response.content)

    def get_model(self) -> BaseChatModel:
        return self._llm

    @staticmethod
    def as_text(content: str | list) -> str:
        """Normalize AIMessage.content: some providers return either a plain
        string or a list of content blocks depending on the response."""
        if isinstance(content, str):
            return content
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        )
