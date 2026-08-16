"""Módulo llm para integração, abstração e contratos estruturados de IA."""

from ctrl_prj.llm.base import LLMProvider
from ctrl_prj.llm.contract import clean_llm_json, execute_analysis
from ctrl_prj.llm.exceptions import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMResponseError,
)
from ctrl_prj.llm.factory import get_provider
from ctrl_prj.llm.mock_provider import MockProvider
from ctrl_prj.llm.openai_provider import OpenAIProvider
from ctrl_prj.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from ctrl_prj.llm.schema import AnalysisResult, SEMANTIC_TYPES

__all__ = [
    "LLMProvider",
    "MockProvider",
    "OpenAIProvider",
    "get_provider",
    "LLMError",
    "LLMAuthenticationError",
    "LLMConnectionError",
    "LLMResponseError",
    "AnalysisResult",
    "SEMANTIC_TYPES",
    "SYSTEM_PROMPT",
    "build_user_prompt",
    "clean_llm_json",
    "execute_analysis",
]
