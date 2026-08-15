"""Provedor Mock de LLM para testes automatizados e execuções isoladas."""

from typing import List, Optional, Tuple

from ctrl_prj.llm.base import LLMProvider

DEFAULT_MOCK_JSON_RESPONSE = """{
  "name": "Mock Project",
  "type": "application",
  "description": "Projeto fictício para testes automatizados.",
  "purpose": "Validar pipeline sem chamadas de rede.",
  "languages": ["Python"],
  "technologies": ["pytest", "pydantic"],
  "confidence": 1.0
}"""


class MockProvider(LLMProvider):
    """Provedor fictício que retorna respostas controladas sem acesso à rede."""

    def __init__(
        self,
        default_response: str = DEFAULT_MOCK_JSON_RESPONSE,
        responses: Optional[List[str]] = None,
    ):
        self.default_response = default_response
        self._responses_queue = list(responses) if responses else []
        self.history: List[Tuple[str, str]] = []
        self.call_count: int = 0

    def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Registra a chamada e retorna a próxima resposta da fila ou a padrão."""
        self.call_count += 1
        self.history.append((prompt, system_prompt))

        if self._responses_queue:
            return self._responses_queue.pop(0)

        return self.default_response

    @property
    def last_prompt(self) -> Optional[str]:
        """Retorna o último prompt enviado."""
        return self.history[-1][0] if self.history else None

    @property
    def last_system_prompt(self) -> Optional[str]:
        """Retorna o último system_prompt enviado."""
        return self.history[-1][1] if self.history else None
