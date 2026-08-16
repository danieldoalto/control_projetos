"""Execução e validação do contrato de comunicação com o LLM."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Optional
from pydantic import ValidationError

from ctrl_prj.llm.base import LLMProvider
from ctrl_prj.llm.exceptions import LLMResponseError
from ctrl_prj.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from ctrl_prj.llm.schema import AnalysisResult

if TYPE_CHECKING:
    from ctrl_prj.analyzer.models import LLMContext



def clean_llm_json(raw_text: str) -> str:
    """Extrai e limpa a string JSON de respostas que possam conter markdown ou texto envolvente."""
    text = raw_text.strip()

    # 1. Se estiver envolto em blocos de código ```json ... ``` ou ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    # 2. Se houver texto antes ou depois do primeiro '{' e último '}'
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]

    return text.strip()


def execute_analysis(
    context: LLMContext,
    provider: LLMProvider,
    max_retries: int = 2,
) -> AnalysisResult:
    """Executa a análise da entidade utilizando o LLM Provider e valida o contrato com Pydantic.

    Implementa política de retry caso o modelo retorne JSON malformado ou fora do schema.

    Args:
        context: Contexto estruturado montado pelo ContextBuilder.
        provider: Provedor de LLM configurado.
        max_retries: Número máximo de tentativas de reexecução em caso de resposta inválida.

    Returns:
        AnalysisResult validado e tipado.

    Raises:
        LLMResponseError: Se o LLM falhar em retornar um JSON válido após todas as tentativas.
    """
    user_prompt = build_user_prompt(context)
    last_error: Optional[Exception] = None
    last_raw_response: str = ""

    for attempt in range(max_retries + 1):
        try:
            raw_response = provider.generate_response(
                prompt=user_prompt,
                system_prompt=SYSTEM_PROMPT,
            )
            last_raw_response = raw_response

            cleaned_json = clean_llm_json(raw_response)
            
            # Valida contra o schema Pydantic
            result = AnalysisResult.model_validate_json(cleaned_json)
            result.raw_response = raw_response
            return result

        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            # Ajusta prompt para a próxima tentativa se houver retry
            if attempt < max_retries:
                user_prompt += (
                    f"\n\n[ATENÇÃO: A resposta anterior foi inválida. Erro: {exc}. "
                    "Por favor, responda OBRIGATORIAMENTE apenas com um objeto JSON estritamente válido.]"
                )

    raise LLMResponseError(
        f"Falha ao validar a resposta do LLM após {max_retries + 1} tentativas. "
        f"Último erro: {last_error}. Resposta bruta: {last_raw_response[:200]}"
    )
