"""Testes automatizados para os provedores e abstrações de LLM."""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from ctrl_prj.config.settings import LLMConfig
from ctrl_prj.llm import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMProvider,
    LLMResponseError,
    MockProvider,
    OpenAIProvider,
    get_provider,
)


def test_mock_provider_basic():
    """Testa MockProvider com resposta padrão e histórico."""
    provider = MockProvider(default_response="teste resposta")
    assert isinstance(provider, LLMProvider)
    assert provider.call_count == 0

    resp = provider.generate_response("prompt 1", system_prompt="sys 1")
    assert resp == "teste resposta"
    assert provider.call_count == 1
    assert provider.last_prompt == "prompt 1"
    assert provider.last_system_prompt == "sys 1"


def test_mock_provider_queue():
    """Testa MockProvider com fila sequencial de respostas."""
    provider = MockProvider(responses=["resp 1", "resp 2"])
    assert provider.generate_response("p1") == "resp 1"
    assert provider.generate_response("p2") == "resp 2"
    # Fila acabou, retorna a default
    assert "Mock Project" in provider.generate_response("p3")


def test_factory_get_provider():
    """Testa factory instanciando os provedores corretos."""
    # Mock
    p_mock = get_provider(LLMConfig(provider="mock"))
    assert isinstance(p_mock, MockProvider)

    # OpenAI
    p_openai = get_provider(LLMConfig(provider="openai", model="gpt-4o"))
    assert isinstance(p_openai, OpenAIProvider)
    assert p_openai.base_url == "https://api.openai.com/v1"

    # OpenRouter
    p_openrouter = get_provider(LLMConfig(provider="openrouter", model="anthropic/claude-3.5-sonnet"))
    assert isinstance(p_openrouter, OpenAIProvider)
    assert p_openrouter.base_url == "https://openrouter.ai/api/v1"

    # Ollama
    p_ollama = get_provider(LLMConfig(provider="ollama", model="llama3.2"))
    assert isinstance(p_ollama, OpenAIProvider)
    assert p_ollama.base_url == "http://localhost:11434/v1"

    # Provedor inválido
    with pytest.raises(LLMError) as exc_info:
        get_provider(LLMConfig(provider="provedor_que_nao_existe"))
    assert "não é suportado" in str(exc_info.value)


def test_openai_provider_missing_api_key(monkeypatch):
    """Garante erro de autenticação quando a chave exigida não existe no ambiente."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIProvider(provider_name="openai", api_key=None, api_key_env="OPENAI_API_KEY")

    with pytest.raises(LLMAuthenticationError) as exc_info:
        provider.generate_response("hello")
    assert "Chave de API não encontrada" in str(exc_info.value)


def test_openai_provider_successful_request():
    """Testa montagem de requisição e parsing de resposta no OpenAIProvider."""
    provider = OpenAIProvider(
        api_key="sk-test-12345",
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=1000,
    )

    mock_response_json = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"name": "App Test", "type": "cli"}',
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_json

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        result = provider.generate_response("Meu prompt", system_prompt="Voce e um assistente")
        assert result == '{"name": "App Test", "type": "cli"}'

        # Verifica argumentos passados no POST
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.openai.com/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test-12345"
        payload = kwargs["json"]
        assert payload["model"] == "gpt-4o-mini"
        assert payload["temperature"] == 0.1
        assert payload["max_tokens"] == 1000
        assert payload["messages"] == [
            {"role": "system", "content": "Voce e um assistente"},
            {"role": "user", "content": "Meu prompt"},
        ]


def test_openai_provider_connection_error():
    """Testa tratamento de erro de conexão/timeout."""
    provider = OpenAIProvider(api_key="sk-test")

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(LLMConnectionError) as exc_info:
            provider.generate_response("prompt")
        assert "Falha de conexão" in str(exc_info.value)


def test_openai_provider_http_errors():
    """Testa tratamento de erros de status HTTP (401 e 500)."""
    provider = OpenAIProvider(api_key="sk-test")

    # 401 Unauthorized
    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_401.text = "Unauthorized"
    with patch("httpx.Client.post", return_value=mock_401):
        with pytest.raises(LLMAuthenticationError) as exc_info:
            provider.generate_response("prompt")
        assert "401" in str(exc_info.value)

    # 500 Internal Server Error
    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_500.text = "Server Error"
    with patch("httpx.Client.post", return_value=mock_500):
        with pytest.raises(LLMResponseError) as exc_info:
            provider.generate_response("prompt")
        assert "500" in str(exc_info.value)


def test_openai_provider_traffic_log_basic(caplog):
    """Testa emissão de logs de tráfego em nível basic."""
    import logging
    provider = OpenAIProvider(
        api_key="sk-test",
        traffic_log="basic",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Resposta simples"}}]
    }

    with caplog.at_level(logging.INFO):
        with patch("httpx.Client.post", return_value=mock_resp):
            res = provider.generate_response("Pergunta basica")
            assert res == "Resposta simples"

    assert any("[LLM TRAFFIC REQUEST]" in r.message for r in caplog.records)
    assert any("[LLM TRAFFIC RESPONSE]" in r.message for r in caplog.records)
    assert not any("[LLM TRAFFIC FULL PROMPT]" in r.message for r in caplog.records)


def test_openai_provider_traffic_log_full(caplog):
    """Testa emissão de logs de tráfego em nível full."""
    import logging
    provider = OpenAIProvider(
        api_key="sk-test",
        traffic_log="full",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Resposta completa detalhada"}}]
    }

    with caplog.at_level(logging.INFO):
        with patch("httpx.Client.post", return_value=mock_resp):
            res = provider.generate_response("Pergunta completa", system_prompt="Prompt do sistema")
            assert res == "Resposta completa detalhada"

    assert any("[LLM TRAFFIC REQUEST]" in r.message for r in caplog.records)
    assert any("[LLM TRAFFIC RESPONSE]" in r.message for r in caplog.records)
    assert any("[LLM TRAFFIC FULL PROMPT]" in r.message for r in caplog.records)
    assert any("[LLM TRAFFIC FULL RESPONSE]" in r.message for r in caplog.records)

