"""Módulo llm para integração e abstração de provedores de IA."""

from ctrl_prj.llm.base import LLMProvider
from ctrl_prj.llm.exceptions import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMResponseError,
)
from ctrl_prj.llm.factory import get_provider
from ctrl_prj.llm.mock_provider import MockProvider
from ctrl_prj.llm.openai_provider import OpenAIProvider

__all__ = [
    "LLMProvider",
    "MockProvider",
    "OpenAIProvider",
    "get_provider",
    "LLMError",
    "LLMAuthenticationError",
    "LLMConnectionError",
    "LLMResponseError",
]
