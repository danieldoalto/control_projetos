"""Definição de Prompts e templates para interação com o LLM."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ctrl_prj.analyzer.models import LLMContext


SYSTEM_PROMPT = """Você é um Analista de Código Especialista em arquitetura de software e catalogação técnica de projetos.
Sua missão é analisar os fatos técnicos e estruturais fornecidos sobre um projeto/script e gerar uma interpretação semântica concisa, precisa e de alta fidelidade.

Regras obrigatórias:
1. Responda ESTRITAMENTE com um único objeto JSON válido.
2. NÃO inclua nenhum texto antes ou depois do JSON.
3. NÃO use blocos markdown nem tags envolventes se possível (retorne apenas o JSON puro).
4. Tipos semânticos sugeridos para o campo "type":
   - application (aplicação completa/sistema)
   - library (biblioteca/pacote reutilizável)
   - utility (utilitário específico)
   - script (script isolado/automação simples)
   - service (serviço backend/API)
   - web (aplicação ou frontend web)
   - cli (ferramenta de linha de comando)
   - automation (script ou pipeline de automação/devops)
   - infrastructure (código de infraestrutura/deploy/docker)
   - experiment (código experimental/POC)
   - unknown (não foi possível determinar com segurança)
5. O campo "tags" DEVE conter de 2 a 4 palavras-chave conceituais em minúsculas que resumam o DOMÍNIO, OBJETIVO e FUNCIONALIDADE CENTRAL do projeto (ex: editor de markdown -> ["editor", "markdown", "texto"]; bot de mensagens -> ["bot", "telegram", "chat"]; controle de energia -> ["energia", "shutdown", "remoto"]; servidor mcp de notas -> ["mcp", "obsidian", "notas"]).

O JSON DEVE conter exatamente os seguintes campos:
{
  "name": "Nome representativo do projeto ou script",
  "type": "tipo_semantico",
  "description": "Resumo de 1 ou 2 frases sobre o que o projeto faz.",
  "purpose": "Qual o propósito prático ou problema que este código resolve.",
  "languages": ["Linguagem1", "Linguagem2"],
  "technologies": ["Tech1", "Tech2"],
  "tags": ["conceito_objetivo1", "conceito_objetivo2", "conceito_objetivo3"],
  "confidence": 1.0
}
"""




def build_user_prompt(context: LLMContext) -> str:
    """Constrói o prompt do usuário a partir do LLMContext de forma estruturada e econômica."""
    sections = []

    # 1. Informações básicas da entidade
    sections.append(f"# Entidade: {context.entity_info.get('name', 'Desconhecido')}")
    sections.append(f"Tipo base: {context.entity_info.get('type', 'project')}")
    sections.append(f"Operação: {context.operation.upper()}")

    # 2. Seção de Atualização (Update)
    if context.operation == "update":
        sections.append("\n## Contexto da Análise Anterior")
        if context.previous_analysis:
            prev_json = json.dumps(context.previous_analysis, ensure_ascii=False, indent=2)
            sections.append(f"```json\n{prev_json}\n```")

        if context.changes:
            sections.append("\n## Alterações Detectadas desde a Última Análise")
            changes_json = json.dumps(context.changes, ensure_ascii=False, indent=2)
            sections.append(f"```json\n{changes_json}\n```")
            sections.append(
                "Atenção: Retorne o ESTADO ATUAL COMPLETO do projeto, incorporando as mudanças acima."
            )

    # 3. Arquivos de Contexto (README, manifests, configs)
    if context.context_files_content:
        sections.append("\n## Arquivos de Contexto e Documentação")
        for rel_path, content in context.context_files_content.items():
            sections.append(f"### Arquivo: {rel_path}\n{content}\n")

    # 4. Fatos Estruturais dos Arquivos de Código
    if context.file_structure:
        sections.append("\n## Estrutura de Código (Fatos Técnicos)")
        for rel_path, struct in context.file_structure.items():
            parts = [f"### Arquivo: {rel_path} ({struct.get('lines_count', 0)} linhas)"]
            if struct.get("imports"):
                parts.append(f"- Imports: {', '.join(struct['imports'])}")
            if struct.get("classes"):
                parts.append(f"- Classes/Tipos: {', '.join(struct['classes'])}")
            if struct.get("functions"):
                parts.append(f"- Funções: {', '.join(struct['functions'])}")
            if struct.get("exports"):
                parts.append(f"- Exports/Shebang: {', '.join(struct['exports'])}")
            sections.append("\n".join(parts))

    sections.append(
        "\nCom base exclusivamente nos fatos e documentação acima, gere a análise no formato JSON solicitado."
    )

    return "\n\n".join(sections)
