"""Testes automatizados para o contrato estruturado de comunicação com o LLM."""

import pytest
from pydantic import ValidationError

from ctrl_prj.analyzer import LLMContext
from ctrl_prj.llm import (
    AnalysisResult,
    LLMResponseError,
    MockProvider,
    build_user_prompt,
    clean_llm_json,
    execute_analysis,
)


def test_clean_llm_json_variants():
    """Testa limpeza de JSON com blocos markdown e textos extras."""
    # 1. JSON puro
    raw1 = '{"name": "App", "type": "cli"}'
    assert clean_llm_json(raw1) == raw1

    # 2. JSON com bloco markdown ```json ... ```
    raw2 = "```json\n{\n  \"name\": \"App\"\n}\n```"
    assert clean_llm_json(raw2) == '{\n  "name": "App"\n}'

    # 3. JSON com texto introdutório e conclusivo
    raw3 = "Olá, aqui está o resultado da análise:\n{\"name\": \"App\"}\nObrigado!"
    assert clean_llm_json(raw3) == '{"name": "App"}'


def test_analysis_result_validation():
    """Testa validação de schema do AnalysisResult com Pydantic."""
    valid_data = {
        "name": "Control Project",
        "type": "cli",
        "description": "Catalogador de projetos",
        "purpose": "Organizar o filesystem",
        "languages": ["Python"],
        "technologies": ["pydantic", "sqlite3"],
        "confidence": 0.95,
    }

    result = AnalysisResult(**valid_data)
    assert result.name == "Control Project"
    assert result.confidence == 0.95

    # Erro por falta de campo obrigatório (purpose)
    invalid_data = valid_data.copy()
    del invalid_data["purpose"]
    with pytest.raises(ValidationError):
        AnalysisResult(**invalid_data)

    # Erro de confidence fora do range (0.0 a 1.0)
    invalid_conf = valid_data.copy()
    invalid_conf["confidence"] = 1.5
    with pytest.raises(ValidationError):
        AnalysisResult(**invalid_conf)


def test_build_user_prompt_initial_and_update():
    """Testa montagem de prompt para initial e update."""
    # Initial
    ctx_initial = LLMContext(
        operation="initial",
        entity_info={"name": "meu_app", "type": "project"},
        file_structure={"main.py": {"lines_count": 10, "functions": ["run"]}},
        context_files_content={"README.md": "# Doc"},
    )
    prompt_initial = build_user_prompt(ctx_initial)
    assert "meu_app" in prompt_initial
    assert "INITIAL" in prompt_initial
    assert "main.py" in prompt_initial
    assert "README.md" in prompt_initial

    # Update
    ctx_update = LLMContext(
        operation="update",
        entity_info={"name": "meu_app", "type": "project"},
        file_structure={},
        context_files_content={},
        previous_analysis={"name": "meu_app_antigo", "type": "cli"},
        changes={"added": ["new.py"]},
    )
    prompt_update = build_user_prompt(ctx_update)
    assert "UPDATE" in prompt_update
    assert "meu_app_antigo" in prompt_update
    assert "new.py" in prompt_update


def test_execute_analysis_success():
    """Testa execução bem-sucedida do contrato com MockProvider."""
    valid_json = """```json
{
  "name": "Super CLI",
  "type": "cli",
  "description": "Ferramenta de automação de projetos.",
  "purpose": "Acelerar fluxos de desenvolvimento.",
  "languages": ["Python"],
  "technologies": ["pytest"],
  "confidence": 1.0
}
```"""
    provider = MockProvider(default_response=valid_json)
    ctx = LLMContext(
        operation="initial",
        entity_info={"name": "Super CLI", "type": "project"},
        file_structure={},
        context_files_content={},
    )

    result = execute_analysis(ctx, provider)
    assert isinstance(result, AnalysisResult)
    assert result.name == "Super CLI"
    assert result.type == "cli"
    assert result.confidence == 1.0
    assert provider.call_count == 1


def test_execute_analysis_retry_mechanism():
    """Testa mecanismo de retry quando a primeira resposta é inválida."""
    invalid_json = "Resposta em texto que não é JSON"
    valid_json = """{
  "name": "Recovered App",
  "type": "application",
  "description": "App recuperado no retry.",
  "purpose": "Testar retry.",
  "languages": ["Python"],
  "technologies": [],
  "confidence": 0.8
}"""
    provider = MockProvider(responses=[invalid_json, valid_json])
    ctx = LLMContext(
        operation="initial",
        entity_info={"name": "Recovered App", "type": "project"},
        file_structure={},
        context_files_content={},
    )

    result = execute_analysis(ctx, provider, max_retries=2)
    assert result.name == "Recovered App"
    assert provider.call_count == 2


def test_execute_analysis_max_retries_exceeded():
    """Testa falha definitiva quando todas as tentativas retornam JSON inválido."""
    invalid_json = "Texto invalido permanente"
    provider = MockProvider(default_response=invalid_json)
    ctx = LLMContext(
        operation="initial",
        entity_info={"name": "Failed App", "type": "project"},
        file_structure={},
        context_files_content={},
    )

    with pytest.raises(LLMResponseError) as exc_info:
        execute_analysis(ctx, provider, max_retries=1)
    assert "Falha ao validar a resposta do LLM" in str(exc_info.value)
    assert provider.call_count == 2
