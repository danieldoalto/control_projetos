"""Schema de validação de dados para as análises geradas pelo LLM."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# Tipos semânticos sugeridos pela especificação
SEMANTIC_TYPES = (
    "application",
    "library",
    "utility",
    "script",
    "service",
    "web",
    "cli",
    "automation",
    "infrastructure",
    "experiment",
    "unknown",
)


class AnalysisResult(BaseModel):
    """Contrato tipado e validado da análise de uma entidade gerada pelo LLM."""
    name: str = Field(
        ...,
        description="Nome representativo do projeto ou script",
    )
    type: str = Field(
        default="unknown",
        description="Tipo semântico (application, library, utility, script, service, web, cli, automation, infrastructure, experiment, unknown)",
    )
    description: str = Field(
        ...,
        description="Resumo claro e conciso (1 ou 2 frases) sobre o que é o projeto",
    )
    purpose: str = Field(
        ...,
        description="Objetivo do código ou problema prático que ele resolve",
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Lista de linguagens de programação principais identificadas",
    )
    technologies: List[str] = Field(
        default_factory=list,
        description="Frameworks, bibliotecas, ferramentas ou tecnologias chave detectadas",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Lista de 1 a 4 tags conceituais curtas (ex: ['fastapi', 'docker', 'backend'])",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Grau de confiança da IA na análise gerada (entre 0.0 e 1.0)",
    )
    raw_response: Optional[str] = Field(
        default=None,
        description="Texto bruto retornado pelo LLM para fins de auditoria",
    )

