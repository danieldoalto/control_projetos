# `ctrl_prj`

Catalogador contínuo, determinístico e inteligente de projetos e códigos no filesystem.

---

## 🎯 Objetivo e Visão Geral

`ctrl_prj` localiza, categoriza, analisa estruturalmente e mantém uma memória persistente de projetos, coleções e scripts distribuídos em diferentes locais do sistema de arquivos.

O sistema opera de forma estritamente **incremental** e **econômica**: apenas arquivos relevantes novos ou modificados passam por análise semântica via IA (LLM), persistindo tudo em banco SQLite e gerando relatórios Markdown descartáveis e recriáveis.

---

## 🧱 Princípios de Design

* **Simplicidade & Determinismo:** Fingerprint SHA-256 reprodutível (`relative_path + file_hash`).
* **Modularidade Estrita:** Separação clara de responsabilidades (*Scanner* coleta fatos → *Analyzer* prepara contexto → *LLM* interpreta → *SQLite* memoriza → *Reporter* apresenta).
* **Incrementalidade Real:** Se o fingerprint não mudou, o LLM não é chamado.
* **Economia de Tokens:** Envio apenas de metadados estruturais leves (AST/imports/classes/funções) e arquivos de contexto essenciais (README, pyproject, etc.).

---

## 🏗️ Arquitetura

```text
                    ┌──────────────┐
                    │  config.yml  │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    SCAN      │ ── (Coleta fatos, calcula hashes)
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   SQLite     │ ── (Memoriza estado e histórico)
                    └──────┬───────┘
                           │  (new / changed)
                           ▼
                    ┌──────────────┐
                    │   ANALYZE    │ ── (Monta contexto otimizado)
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ LLM Provider │ ── (Interpretação e validação de schema)
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   SQLite     │ ── (Grava análises consolidadas)
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   REPORT     │ ── (Gera Markdown derivado)
                    └──────┬───────┘
                           │
                           ▼
                 reports/
                 ├── INDEX.md
                 └── projects/
                     ├── meu-projeto.md
                     └── ...
```

---

## 🚀 Instalação e Ambiente

O projeto utiliza [`uv`](https://docs.astral.sh/uv/) para gerenciamento de dependências e ambiente Python (3.11+):

```bash
# Clonar o repositório
git clone <url-do-repositorio>
cd control_projetos

# Sincronizar dependências e criar o ambiente virtual
uv sync
```

---

## ⚙️ Configuração (`config.yml`)

Copie o arquivo de exemplo para criar a sua configuração local:

```bash
cp config.example.yml config.yml
```

Exemplo de estrutura:

```yaml
# Raízes a serem monitoradas pelo scanner
roots:
  - "~/projetos"
  - "~/scripts"

# Banco de dados SQLite
database:
  path: "~/.ctrl_prj/data.db"

# Provedor de LLM (openai, openrouter, ollama, lmstudio, mock)
llm:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"
  temperature: 0.0
  max_tokens: 2000

# Geração de Relatórios
reporter:
  output_dir: "./reports"

# Exclusões padrão
exclusions:
  - ".git"
  - "node_modules"
  - ".venv"
  - "__pycache__"
  - "target"
  - "dist"
```

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

## 🛠️ Comandos da CLI

Você pode executar os comandos da CLI diretamente com `uv run ctrl_prj`:

### 1. `ctrl_prj scan`
Descobre entidades, varre arquivos relevantes, calcula hashes e atualiza o estado no SQLite. Não utiliza LLM.

```bash
uv run ctrl_prj scan

# Forçar sincronização e purga de arquivos excluídos em todas as entidades:
uv run ctrl_prj scan --force   # ou -f
```

### 2. `ctrl_prj analyze`
Consulta entidades pendentes (`new` ou `changed`) no SQLite, extrai a estrutura de código, monta o contexto e executa a análise com o LLM configurado.

```bash
uv run ctrl_prj analyze

# Forçar reanálise com IA de todos os projetos (mesmo já analisados):
uv run ctrl_prj analyze --force # ou -f
```

### 3. `ctrl_prj report`
Gera os relatórios individuais (`reports/projects/*.md`) e o catálogo mestre ([`reports/INDEX.md`](reports/INDEX.md)) agrupado por categorias semânticas.

```bash
uv run ctrl_prj report

# Especificando pasta de saída customizada:
uv run ctrl_prj report -o ./meus_relatorios
```

### 4. `ctrl_prj run`
Executa o pipeline completo de ponta a ponta (`scan` → `analyze` → `report`):

```bash
uv run ctrl_prj run

# Pipeline completo forçando re-escaneamento e reanálise de tudo:
uv run ctrl_prj run --force     # ou -f
```


---

## 🧪 Testes Automatizados

A suíte de testes cobre testes unitários e de integração de ponta a ponta:

```bash
uv run pytest
```

---

## 📁 Estrutura do Código

```text
src/ctrl_prj/
├── cli/          # Comandos da CLI (scan, analyze, report, run)
├── config/       # Validação e carregamento de configurações com Pydantic
├── discovery/    # Identificação de entidades no filesystem e heurísticas
├── scanner/      # Varredura de arquivos e orquestração de scan
├── fingerprint/  # Hashes SHA-256 e cálculo de deltas
├── analyzer/     # Análise estrutural leve (AST) e montagem de contexto
├── llm/          # Abstrações de provedores LLM e validação de schema
├── memory/       # Repositórios SQLite e persistência
└── reporter/     # Gerador de relatórios Markdown e índice consolidado
```
