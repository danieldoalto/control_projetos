"""Provedor de LLM compatível com a API padrão OpenAI (OpenAI, OpenRouter, Ollama, LM Studio)."""

import os
import time
from typing import Any, Dict, List, Optional
import httpx

from ctrl_prj.config.settings import LLMConfig
from ctrl_prj.llm.base import LLMProvider
from ctrl_prj.llm.exceptions import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMResponseError,
)


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_LMSTUDIO_BASE_URL = "http://localhost:1234/v1"


class OpenAIProvider(LLMProvider):
    """Provedor de chat completions utilizando a especificação de API da OpenAI."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        timeout: float = 60.0,
        provider_name: str = "openai",
    ):
        self.model = model
        self.api_key_env = api_key_env
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.provider_name = provider_name.lower().strip()

        # Determina base_url
        if base_url:
            self.base_url = base_url.rstrip("/")
        elif self.provider_name == "openrouter":
            self.base_url = DEFAULT_OPENROUTER_BASE_URL
        elif self.provider_name == "ollama":
            self.base_url = DEFAULT_OLLAMA_BASE_URL
        elif self.provider_name == "lmstudio":
            self.base_url = DEFAULT_LMSTUDIO_BASE_URL
        else:
            self.base_url = DEFAULT_OPENAI_BASE_URL

        # Determina API key
        if api_key:
            self.api_key = api_key
        else:
            env_key = os.getenv(self.api_key_env)
            if env_key:
                self.api_key = env_key
            elif self.provider_name in {"ollama", "lmstudio"}:
                self.api_key = "local-dummy-key"
            else:
                self.api_key = ""

    @classmethod
    def from_config(cls, config: LLMConfig) -> "OpenAIProvider":
        """Instancia o provedor a partir de um objeto LLMConfig."""
        return cls(
            model=config.model,
            api_key_env=config.api_key_env,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            provider_name=config.provider,
        )

    def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Envia a requisição de chat completion ao endpoint configurado."""
        if not self.api_key and self.provider_name not in {"ollama", "lmstudio"}:
            raise LLMAuthenticationError(
                f"Chave de API não encontrada na variável de ambiente '{self.api_key_env}' para o provedor '{self.provider_name}'."
            )

        endpoint = f"{self.base_url}/chat/completions"
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        for attempt in range(1, 3):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(endpoint, json=payload, headers=headers)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < 2:
                    time.sleep(1.5)
                    continue
                raise LLMConnectionError(
                    f"Falha de conexão com o provedor LLM ({self.base_url}): {exc}"
                ) from exc
            except Exception as exc:
                raise LLMError(f"Erro inesperado na chamada ao provedor LLM: {exc}") from exc

            if response.status_code in {401, 403}:
                raise LLMAuthenticationError(
                    f"Falha de autenticação no provedor LLM ({response.status_code}): {response.text}"
                )

            if response.status_code != 200:
                if attempt < 2 and response.status_code in {429, 500, 502, 503, 504}:
                    time.sleep(2.0)
                    continue
                raise LLMResponseError(
                    f"Erro na resposta do provedor LLM (HTTP {response.status_code}): {response.text}"
                )

            try:
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    if attempt < 2:
                        time.sleep(1.0)
                        continue
                    raise LLMResponseError("O provedor LLM retornou uma lista vazia de escolhas ('choices').")

                message = choices[0].get("message", {})
                content = message.get("content") or ""
                if not content and message.get("reasoning_content"):
                    content = message.get("reasoning_content") or ""

                if not content:
                    if attempt < 2:
                        time.sleep(1.0)
                        continue
                    raise LLMResponseError("O provedor LLM retornou um conteúdo vazio na mensagem.")

                return content.strip()
            except LLMError:
                raise
            except Exception as exc:
                raise LLMResponseError(f"Erro ao processar JSON da resposta do provedor LLM: {exc}") from exc

