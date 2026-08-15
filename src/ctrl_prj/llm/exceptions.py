"""Exceções padronizadas para o módulo de LLM."""


class LLMError(Exception):
    """Exceção base para erros na camada de integração com LLMs."""
    pass


class LLMAuthenticationError(LLMError):
    """Lançada quando a chave de API é inválida, ausente ou o acesso foi negado."""
    pass


class LLMConnectionError(LLMError):
    """Lançada em caso de falhas de conexão de rede, resolução de DNS ou timeouts."""
    pass


class LLMResponseError(LLMError):
    """Lançada quando o provedor retorna erros de status HTTP ou resposta inesperada/vazia."""
    pass
