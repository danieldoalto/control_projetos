# `ctrl_prj`

Catalogador contínuo e inteligente de projetos e scripts no filesystem.

## 🎯 Objetivo

`ctrl_prj` localiza, analisa e mantém uma descrição estruturada e atualizada de projetos e códigos em diferentes diretórios, persistindo o estado em SQLite e gerando relatórios em Markdown.

## 🚀 Instalação e Ambiente

O projeto utiliza [`uv`](https://docs.astral.sh/uv/) para gerenciamento de dependências e ambiente virtual.

```bash
# Sincronizar dependências e criar o ambiente virtual (.venv)
uv sync

# Ativar o ambiente virtual (opcional se usar 'uv run')
source .venv/bin/activate
```

## 🛠️ Uso da CLI

Você pode executar a CLI diretamente com `uv run`:

```bash
# Descobrir e atualizar estado do filesystem (sem LLM)
uv run ctrl_prj scan

# Analisar entidades novas ou modificadas com LLM
uv run ctrl_prj analyze

# Gerar relatórios em Markdown a partir do SQLite
uv run ctrl_prj report

# Executar pipeline completo (scan -> analyze -> report)
uv run ctrl_prj run
```

## 🧪 Testes

Para rodar a suíte de testes com `pytest`:

```bash
uv run pytest
```

## 📁 Estrutura Modular

```
ctrl_prj/
├── cli/          # Interface de linha de comando
├── config/       # Carregamento e validação de configurações
├── scanner/      # Coleta de fatos no filesystem
├── discovery/    # Identificação de entidades (projetos/scripts)
├── fingerprint/  # Geração de hashes e fingerprints determinísticos
├── analyzer/     # Extração estrutural e preparação de contexto
├── llm/          # Abstração de provedores LLM
├── memory/       # Persistência e gerenciamento SQLite
└── reporter/     # Geração de relatórios Markdown
```
