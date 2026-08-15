"""Interface abstrata base para provedores de LLM."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Contrato abstrato que todos os provedores de LLM devem implementar."""

    @abstractmethod
    def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Gera uma resposta de texto a partir dos prompts fornecidos.

        Args:
            prompt: Texto da mensagem do usuário / contexto principal.
            system_prompt: Instrução do sistema (opcional).

        Returns:
            str: Resposta gerada pelo modelo.

        Raises:
            LLMError: Em caso de falhas de autenticação, conexão ou resposta.
        """
        pass
