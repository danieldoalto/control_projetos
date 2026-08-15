"""Factory para instanciação de provedores de LLM baseados em configuração."""

from typing import Union

from ctrl_prj.config.settings import AppConfig, LLMConfig
from ctrl_prj.llm.base import LLMProvider
from ctrl_prj.llm.exceptions import LLMError
from ctrl_prj.llm.mock_provider import MockProvider
from ctrl_prj.llm.openai_provider import OpenAIProvider


def get_provider(config: Union[LLMConfig, AppConfig, str]) -> LLMProvider:
    """Retorna uma instância de LLMProvider configurada.

    Args:
        config: Objeto LLMConfig, AppConfig ou string com o nome do provedor.

    Returns:
        LLMProvider pronto para uso.

    Raises:
        LLMError: Se o provedor informado for inválido ou não suportado.
    """
    if isinstance(config, str):
        provider_name = config.lower().strip()
        llm_cfg = LLMConfig(provider=provider_name)
    elif isinstance(config, AppConfig):
        llm_cfg = config.llm
        provider_name = llm_cfg.provider.lower().strip()
    elif isinstance(config, LLMConfig):
        llm_cfg = config
        provider_name = llm_cfg.provider.lower().strip()
    else:
        raise LLMError(f"Tipo de configuração inválido para LLM: {type(config)}")

    if provider_name == "mock":
        return MockProvider()

    if provider_name in {"openai", "openrouter", "ollama", "lmstudio", "generic"}:
        return OpenAIProvider.from_config(llm_cfg)

    raise LLMError(
        f"Provedor de LLM '{provider_name}' não é suportado. "
        "Opções disponíveis: mock, openai, openrouter, ollama, lmstudio."
    )
