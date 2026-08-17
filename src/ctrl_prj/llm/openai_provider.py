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
from ctrl_prj.log import get_logger

logger = get_logger(__name__)


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
        traffic_log: str = "none",
    ):
        self.model = model
        self.api_key_env = api_key_env
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.provider_name = provider_name.lower().strip()
        self.traffic_log = traffic_log.lower().strip()

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
            traffic_log=config.traffic_log,
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

        logger.info(f"Enviando requisição LLM ao provedor '{self.provider_name}' (modelo: {self.model}, endpoint: {endpoint})...")
        logger.debug(f"Payload com {len(messages)} mensagens, prompt ~{len(prompt)} caracteres")

        if self.traffic_log in ("basic", "full"):
            logger.info(
                f"[LLM TRAFFIC REQUEST] Provider={self.provider_name} | Model={self.model} | "
                f"Endpoint={endpoint} | PromptChars={len(prompt)} | MessagesCount={len(messages)}"
            )

        if self.traffic_log == "full":
            logger.info(
                f"[LLM TRAFFIC FULL PROMPT]\n"
                f"--- SYSTEM PROMPT ---\n{system_prompt}\n"
                f"--- USER PROMPT ---\n{prompt}"
            )

        for attempt in range(1, 3):
            start_time = time.perf_counter()
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(endpoint, json=payload, headers=headers)
                latency = time.perf_counter() - start_time
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                latency = time.perf_counter() - start_time
                logger.warning(f"Tentativa {attempt}/2 de conexão com LLM falhou ({latency:.2f}s): {exc}")
                if attempt < 2:
                    time.sleep(1.5)
                    continue
                raise LLMConnectionError(
                    f"Falha de conexão com o provedor LLM ({self.base_url}): {exc}"
                ) from exc
            except Exception as exc:
                latency = time.perf_counter() - start_time
                logger.error(f"Erro inesperado na chamada ao provedor LLM ({latency:.2f}s): {exc}")
                raise LLMError(f"Erro inesperado na chamada ao provedor LLM: {exc}") from exc

            if response.status_code in {401, 403}:
                logger.error(f"Erro de autenticação no provedor LLM (HTTP {response.status_code}, {latency:.2f}s)")
                raise LLMAuthenticationError(
                    f"Falha de autenticação no provedor LLM ({response.status_code}): {response.text}"
                )

            if response.status_code != 200:
                logger.warning(f"Tentativa {attempt}/2 retornou HTTP {response.status_code} em {latency:.2f}s: {response.text[:200]}")
                if attempt < 2 and response.status_code in {429, 500, 502, 503, 504}:
                    time.sleep(2.0)
                    continue
                raise LLMResponseError(
                    f"Erro na resposta do provedor LLM (HTTP {response.status_code}): {response.text}"
                )

            try:
                data = response.json()
                logger.info(f"Resposta LLM recebida com sucesso (HTTP {response.status_code}, {latency:.2f}s)")
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

                stripped_content = content.strip()

                if self.traffic_log in ("basic", "full"):
                    logger.info(
                        f"[LLM TRAFFIC RESPONSE] Status=HTTP {response.status_code} | "
                        f"Latency={latency:.2f}s | ResponseChars={len(stripped_content)}"
                    )

                if self.traffic_log == "full":
                    logger.info(
                        f"[LLM TRAFFIC FULL RESPONSE]\n{stripped_content}"
                    )

                return stripped_content
            except LLMError:
                raise
            except Exception as exc:
                logger.error(f"Formato inesperado na resposta do provedor LLM: {exc}")
                raise LLMResponseError(
                    f"Formato inesperado na resposta do provedor LLM: {exc}. Resposta bruta: {response.text}"
                ) from exc

        raise LLMResponseError("Número máximo de tentativas excedido sem resposta do provedor LLM.")
