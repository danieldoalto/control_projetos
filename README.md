# `ctrl_prj`

Catalogador contínuo, determinístico e inteligente de projetos e códigos no filesystem com enriquecimento via IA e relatórios integrados para Obsidian.

---

## 🎯 Objetivo e Visão Geral

`ctrl_prj` localiza, categoriza, analisa estruturalmente e mantém uma memória persistente de projetos, coleções e scripts distribuídos pelo sistema de arquivos.

O sistema opera de forma estritamente **incremental** e **econômica**:
- Apenas arquivos relevantes novos ou modificados passam por análise semântica via IA (LLM).
- O estado e o histórico de alterações são persistidos em um banco de dados SQLite local.
- Relatórios Markdown derivados são gerados prontos para visualização e navegação em vaults do **Obsidian** (com tags conceituais e índice interativo TOC).
- Suporte nativo e testado para **Linux** e **Windows**.

---

## 🧱 Princípios de Design

* **Simplicidade & Determinismo:** Fingerprint SHA-256 reprodutível (`relative_path + file_hash`).
* **Modularidade Estrita:** Separação clara de responsabilidades (*Scanner* coleta fatos → *Analyzer* prepara contexto estrutural → *LLM* interpreta → *SQLite* memoriza → *Reporter* apresenta).
* **Incrementalidade Real:** Se o fingerprint da entidade não mudou, o LLM não é chamado.
* **Economia de Tokens:** Envio apenas de metadados estruturais leves (AST, imports, classes, funções) e arquivos de contexto essenciais (README, pyproject, package.json, Dockerfile, etc.).
* **Tags Orientadas ao Domínio:** A IA sintetiza tags conceituais que resumem o propósito e a funcionalidade central do projeto.
* **Proteção contra Dependências e Caches:** Detecção automática universal de ambientes virtuais (`pyvenv.cfg`, `site-packages`, `*-env`) e repositórios `.git`.

---

## 🏗️ Arquitetura

```text
                    ┌─────────────────────────┐
                    │ config.yml / .env       │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │          SCAN           │ ── (Varre roots e individual_projects,
                    └────────────┬────────────┘     calcula hashes e fingerprints)
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         SQLite          │ ── (Memoriza estado, delta e histórico)
                    └────────────┬────────────┘
                                 │  (status: new / changed / error)
                                 ▼
                    ┌─────────────────────────┐
                    │         ANALYZE         │ ── (Monta payload leve e estruturado)
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      LLM Provider       │ ── (Interpretação semântica, validação
                    │ (OpenRouter/OpenAI/...) │     de schema e tags de objetivo)
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         SQLite          │ ── (Grava análises consolidadas)
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         REPORT          │ ── (Gera Markdown com frontmatter,
                    └────────────┬────────────┘     tags e TOC para Obsidian)
                                 │
                                 ▼
                  reports/
                  ├── {device}-INDEX.md
                  └── projects/
                      ├── {device}-{projeto-1}.md
                      ├── {device}-{projeto-2}.md
                      └── ...
```

---

## 🚀 Instalação e Ambiente

O projeto utiliza [`uv`](https://docs.astral.sh/uv/) para gerenciamento de dependências e ambiente Python (3.11+):

```bash
# Clonar o repositório
git clone https://github.com/danieldoalto/control_projetos.git
cd control_projetos

# Sincronizar dependências e criar o ambiente virtual
uv sync
```

---

## ⚙️ Configuração (`config.yml` e `.env`)

### 1. Variáveis de Ambiente (`.env`)
Copie o exemplo para configurar suas chaves de API com segurança:

```bash
cp .env.example .env
```

Preencha com a sua chave (exemplo para OpenRouter ou OpenAI):
```env
OPENROUTER_API_KEY=sk-or-v1-sua-chave-aqui
OPENAI_API_KEY=sk-sua-chave-openai-aqui
```

### 2. Arquivo de Configuração (`config.yml`)
Copie o arquivo de exemplo:

```bash
cp config.example.yml config.yml
```

Estrutura das principais opções:

```yaml
# Configurações do Scanner e Descoberta de Projetos
scan:
  # Pastas raízes contêineres (coleções com múltiplos projetos dentro)
  roots:
    - ~/projetos
    - D:/Projetos

  # Pastas ou scripts de projetos individuais diretos (tratados como projeto único)
  individual_projects:
    - ~/PowerControl
    - D:/Projetos/openwebui
    - ~/scripts/backup.sh

  # Diretórios, arquivos e padrões com wildcard a ignorar
  exclusions:
    - .git
    - node_modules
    - .venv
    - venv
    - env
    - "*env*"
    - "*venv*"
    - site-packages
    - dist-packages
    - __pycache__
    - target
    - dist
    - build
    - coverage
    - .cache
    - graphify-out
    - logs
    - package-lock.json
    - "*.lock"

# Configurações de Persistência no SQLite
database:
  path: data.db

# Configurações do Provedor de LLM (openrouter, openai, anthropic, ollama)
llm:
  provider: openrouter
  model: deepseek/deepseek-v4-flash-0731
  api_key_env: OPENROUTER_API_KEY
  temperature: 0.0
  max_tokens: 2000
  traffic_log: basic  # Opções: none (desativado), basic (latência/tamanhos), full (prompt completo)

# Configurações de Geração de Relatórios Markdown
reporter:
  output_dir: reports
  device: notebook  # Identificador deste computador/nó (usado como prefixo)
```

---

## 🎯 Executando em Pastas ou Projetos Específicos (Alvos via CLI)

Todos os comandos (`scan`, `analyze`, `report`, `run`) permitem processar **uma ou mais pastas específicas** passadas diretamente na linha de comando, sem necessidade de editar o `config.yml`:

### Formas de passar os caminhos:
1. **Argumentos posicionais diretos**: `ctrl_prj <comando> <caminho1> <caminho2> ...`
2. **Flag `-p` ou `--paths`**: `ctrl_prj <comando> -p <caminho1> <caminho2> ...`

### Exemplos no Linux / macOS:
```bash
# 1. Escanear apenas um projeto
uv run ctrl_prj scan ~/projetos/meu-app

# 2. Escanear múltiplos projetos
uv run ctrl_prj scan ~/projetos/app1 ~/projetos/app2

# 3. Analisar com IA apenas uma pasta específica
uv run ctrl_prj analyze ~/projetos/meu-app

# 4. Forçar reanálise com IA apenas do projeto alvo
uv run ctrl_prj analyze -f ~/projetos/meu-app

# 5. Gerar relatórios Markdown apenas para a pasta especificada
uv run ctrl_prj report ~/projetos/meu-app

# 6. Executar o fluxo completo (scan -> analyze -> report) em um projeto
uv run ctrl_prj run ~/projetos/meu-app
```

### Exemplos no Windows (PowerShell / CMD):
```powershell
# 1. Escanear apenas a pasta do OpenWebUI
uv run ctrl_prj scan D:\Projetos\openwebui

# 2. Escanear múltiplos projetos usando a flag -p / --paths
uv run ctrl_prj scan -p D:\Projetos\openwebui D:\Projetos\outro-projeto

# 3. Analisar com IA apenas o projeto alvo
uv run ctrl_prj analyze D:\Projetos\openwebui

# 4. Executar o pipeline completo apenas para o projeto alvo
uv run ctrl_prj run D:\Projetos\openwebui
```

---

## 🛠️ Comandos da CLI

Você pode executar os comandos da CLI diretamente com `uv run ctrl_prj`:

### 1. `ctrl_prj scan`
Descobre entidades, varre arquivos relevantes, calcula hashes e atualiza o estado no SQLite. Não utiliza LLM.

```bash
# Escanear todas as raízes e projetos do config.yml:
uv run ctrl_prj scan

# Escanear apenas projetos/pastas específicas:
uv run ctrl_prj scan /caminho/projeto1 /caminho/projeto2
uv run ctrl_prj scan -p /caminho/projeto1

# Forçar sincronização e purga de arquivos excluídos:
uv run ctrl_prj scan --force   # ou -f
```

### 2. `ctrl_prj analyze`
Consulta entidades pendentes (`new`, `changed`, `error`) no SQLite, extrai a estrutura de código, monta o contexto e executa a análise com o LLM configurado.

```bash
# Analisar todas as entidades pendentes:
uv run ctrl_prj analyze

# Analisar apenas uma pasta/projeto específico:
uv run ctrl_prj analyze /caminho/projeto1

# Forçar reanálise de todas as entidades:
uv run ctrl_prj analyze --force # ou -f

# Forçar reanálise de apenas um projeto específico:
uv run ctrl_prj analyze -f /caminho/projeto1
```

### 3. `ctrl_prj report`
Gera os relatórios individuais (`reports/projects/{device}-*.md`) e o catálogo mestre ([`reports/{device}-INDEX.md`](reports/)) agrupado por origens e categorias semânticas.

```bash
# Gerar relatórios para todas as entidades:
uv run ctrl_prj report

# Gerar relatórios apenas para as pastas/projetos especificados:
uv run ctrl_prj report /caminho/projeto1

# Especificando pasta de saída customizada:
uv run ctrl_prj report -o ./meus_relatorios
```

### 4. `ctrl_prj run`
Executa o pipeline completo de ponta a ponta (`scan` → `analyze` → `report`):

```bash
# Pipeline completo para todos os projetos do config.yml:
uv run ctrl_prj run

# Pipeline completo direcionado exclusivamente a um projeto ou pasta:
uv run ctrl_prj run /caminho/meu-projeto

# Pipeline completo forçando re-escaneamento e reanálise:
uv run ctrl_prj run --force     # ou -f
```

---

## 🔍 Opções Globais da CLI

```bash
# Controle do nível de log de tráfego do LLM (none, basic, full)
uv run ctrl_prj --llm-traffic full analyze

# Definir nível de log do sistema e destino (console, file, both, none)
uv run ctrl_prj --log-level DEBUG --log-dest file scan

# Usar arquivo de configuração alternativo
uv run ctrl_prj -c /caminho/outro-config.yml scan
```

---

## 📑 Formato dos Relatórios Gerados

Todos os relatórios gerados são otimizados para navegação visual e busca por tags no **Obsidian**:

### 1. Relatório Individual (`reports/projects/{device}-{projeto}.md`)
```markdown
---
tags:
  - control_project
  - {tag_conceitual_1}
  - {tag_conceitual_2}
  - {tag_conceitual_3}
  - {tag_conceitual_4}
Titulo: Nome do Projeto
Data: 2026-08-17
Resumo: Resumo claro sobre a finalidade e problema que o projeto resolve.
---

```table-of-contents
title: 
style: nestedList # TOC style (nestedList|nestedOrderedList|inlineFirstLevel)
includeLinks: true # Make headings clickable
hideWhenEmpty: false # Hide TOC if no headings are found
debugInConsole: false # Print debug info in Obsidian console
```

# Nome do Projeto
> Resumo executivo da análise.

## 📋 Visão Geral
- **Tipo Semântico:** `service`
- **Caminho no Filesystem:** `/home/usuario/meu_projeto`
- **Status:** `analyzed`
- **Última Análise:** `2026-08-17 12:00:00`

## 🎯 Propósito
Descrição detalhada do objetivo do projeto.

## 🛠️ Tecnologias e Linguagens
...
## 📁 Arquivos Relevantes
...
```

### 2. Catálogo Consolidado (`reports/{device}-INDEX.md`)
O arquivo de índice contém:
- **Sumário Geral:** Métricas detalhadas com separação por cada raiz contêiner (`roots`) e por projetos individuais (`individual_projects`).
- **Seções por Origem:** Blocos separados para cada pasta raiz com suas respectivas categorias semânticas, seguido da seção de projetos individuais diretos.

---

## 🏷️ Classificação Explícita (`.ctrl_prj`)

Qualquer diretório pode conter um arquivo opcional `.ctrl_prj` para sobrepor as heurísticas automáticas:

```ini
# Para forçar classificação como projeto
type=project

# Para coleções com múltiplos projetos internos
type=collection
depth=1

# Para scripts individuais
type=script
name=Meu Script Utilitário
```

---

## 🧪 Testes Automatizados

A suíte de testes cobre testes unitários, validações de configuração, mock de LLM, detecção heurística, proteção contra virtualenvs, suporte cross-platform e integração End-to-End:

```bash
uv run pytest
```

---

## 📁 Estrutura do Código

```text
src/ctrl_prj/
├── cli/          # Interface CLI com argparse (scan, analyze, report, run e paths)
├── config/       # Validação e carregamento de configurações com Pydantic e .env
├── discovery/    # Identificação de entidades no filesystem, heurísticas e manifestos
├── scanner/      # Varredura de arquivos e orquestração de scan (roots e individuais)
├── fingerprint/  # Hashes SHA-256 e cálculo de deltas
├── analyzer/     # Análise estrutural leve (AST) e montagem de contexto
├── llm/          # Abstrações de provedores LLM (OpenAI, OpenRouter, Mock) e schemas
├── memory/       # Repositórios SQLite, models e migrações de schema
└── reporter/     # Gerador de relatórios Markdown, frontmatter, TOC e índice consolidado
```
