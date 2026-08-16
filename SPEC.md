# 1. ESPECIFICAÇÃO GERAL — `ctrl_prj`

## 1.1. Identificação

**Nome:** `ctrl_prj`

**Objetivo:** catalogar, identificar e manter uma descrição atualizada e semanticamente rica de projetos e pequenos códigos existentes em diferentes locais do filesystem.

**Linguagens analisadas inicialmente:**

- Python
- Rust
- Bash / Shell
- JavaScript
- TypeScript

**Usuários:** um único usuário.

**Ambiente:** principalmente local, podendo trabalhar sobre filesystem acessível através de rede/montagem.

---

# 2. Princípios do projeto

### Simplicidade
O sistema deve evitar complexidade desnecessária.

### Modularidade
O código deve ser dividido por responsabilidades para facilitar manutenção e evolução.

### Incrementalidade
Nenhum projeto deve ser analisado novamente quando não houver alteração em seu fingerprint estrutural.

### Economia de tokens
O LLM deve receber somente o contexto necessário (AST, metadados de arquivos e manifestos essenciais).

### Determinismo
Scanner, fingerprint e geração de relatórios devem ser estritamente determinísticos.

### Separação de responsabilidades

```
Scanner
    → coleta fatos e calcula fingerprints

Analyzer
    → prepara contexto estrutural

LLM
    → interpreta semântica, propósito e tags

SQLite
    → memoriza estado, histórico e análises

Reporter
    → apresenta relatórios Markdown para Obsidian
```

---

# 3. Arquitetura

```
                    ┌─────────────────────────┐
                    │ config.yml / .env       │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │          SCAN           │ ── (Varre roots e individual_projects)
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         SQLite          │ ── (Memoriza estado e histórico)
                    └────────────┬────────────┘
                                 │
                          (new / changed)
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         ANALYZE         │ ── (Monta payload estruturado leve)
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      LLM Provider       │ ── (Interpretação e tags conceituais)
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         SQLite          │ ── (Grava análises consolidadas)
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         REPORT          │ ── (Gera Markdown com frontmatter & TOC)
                    └────────────┬────────────┘
                                 │
                                 ▼
                  reports/
                  ├── {device}-INDEX.md
                  └── projects/
                      ├── {device}-projeto1.md
                      ├── {device}-projeto2.md
                      └── ...
```

---

# 4. CLI

Comandos obrigatórios:

```bash
ctrl_prj scan [--force / -f]
ctrl_prj analyze [--force / -f]
ctrl_prj report [-o output_dir]
ctrl_prj run [--force / -f]
```

### `scan`
Descobre entidades (em `roots` e `individual_projects`), varre arquivos, calcula hashes/fingerprints e atualiza o estado no SQLite. Não utiliza LLM.
- Flag `--force` / `-f`: Força re-escaneamento completo e purga arquivos excluídos de todas as entidades.

### `analyze`
Analisa entidades pendentes (`new`, `changed`, `error`). Monta o contexto estruturado e utiliza o provedor LLM configurado.
- Flag `--force` / `-f`: Força reanálise com IA de todas as entidades, mesmo as já analisadas.

### `report`
Gera os relatórios Markdown individuais e o índice consolidado a partir do banco SQLite. Não utiliza LLM.

### `run`
Executa o pipeline completo integrado:
```
scan → analyze → report
```
- Flag `--force` / `-f`: Executa o pipeline forçando o re-escaneamento e reanálise total.

---

# 5. Descoberta de Projetos e Raízes

O sistema suporta duas formas complementares de catalogação:

```yaml
scan:
  # 1. Pastas raízes contêineres (contêm múltiplos subprojetos dentro)
  roots:
    - ~/projetos
    - ~/scripts

  # 2. Projetos individuais diretos (pastas ou scripts tratados como uma única entidade)
  individual_projects:
    - ~/PowerControl
    - ~/servicos-dashboard
    - ~/scripts/backup.sh
```

As raízes contêineres e projetos individuais são independentes e devidamente identificados e segregados nos relatórios.

---

# 6. Classificação Explícita (`.ctrl_prj`)

Arquivo opcional presente em qualquer diretório que necessite de classificação explícita para sobrepor as heurísticas automáticas.

Formato:

```ini
type=project
```

ou:

```ini
type=collection
depth=1
```

ou:

```ini
type=script
name=Meu script
```

Tipos suportados:
```
project
collection
script
```

Configuração explícita tem precedência absoluta sobre as heurísticas automáticas de detecção.

---

# 7. Heurísticas de Descoberta

Quando não existe `.ctrl_prj`, o scanner utiliza heurísticas de detecção de manifestos e arquivos raiz:

Indicadores de projeto incluem:

```
pyproject.toml
Cargo.toml
package.json
go.mod
pom.xml
CMakeLists.txt
README.md
código reconhecido
```

Uma entidade identificada engloba sua árvore interna completa, isolando-a de diretórios superiores.

---

# 8. Arquivos Suportados

### Código
```
.py
.rs
.sh
.bash
.js
.mjs
.cjs
.ts
.tsx
```

### Arquivos de Contexto
Manifestos, documentação e arquivos de configuração estrutural:

```
README.md
pyproject.toml
requirements.txt
Cargo.toml
package.json
tsconfig.json
Dockerfile
*.yaml
*.yml
*.json
*.toml
*.sql
Makefile
```

A lista de extensões e arquivos é configurável via `config.yml`.

---

# 9. Exclusões

Diretórios, arquivos e padrões de lock ignorados por padrão:

```
.git
node_modules
.venv
venv
__pycache__
target
dist
build
coverage
.cache
.claude
.cursor
.gemini
package-lock.json
pnpm-lock.yaml
yarn.lock
```

Suporte completo a padrões wildcard (ex: `*.lock`, `*.tmp`, `*.bak`).
Também são ignorados binários, imagens, vídeos e arquivos temporários. Symlinks não são seguidos por padrão.

---

# 10. Análise Estrutural Local

O analisador Python extrai informações estruturais leves:

```
arquivo
linguagem
tamanho (bytes)
linhas
imports
classes
funções / métodos
exports
```

A análise é deliberadamente leve (baseada em AST e regex) para não sobrecarregar o pipeline.

---

# 11. Fingerprint e Integridade

Cada arquivo relevante possui um hash SHA-256 (`file_hash`).

O **fingerprint da entidade** é gerado de forma determinística:

```
SHA-256( (relative_path + ":" + file_hash) ordenados alfabeticamente )
```

Garante que qualquer adição, exclusão ou modificação em arquivos relevantes resulte em um novo fingerprint.

---

# 12. Incrementalidade e Deltas

O sistema monitora alterações classificando os arquivos em:

```
UNCHANGED
ADDED
MODIFIED
DELETED
```

- Se o fingerprint da entidade não mudou → **não chama o LLM**.
- Se mudou → compara hashes individuais e envia ao LLM apenas o delta e contexto relevante.

---

# 13. Estados da Entidade

As entidades assumem os seguintes estados no SQLite:

```
new        → Descoberta recentemente, aguarda análise
unchanged  → Inalterada desde o último scan
changed    → Modificada no filesystem, aguarda reanálise
analyzed   → Analisada pelo LLM com sucesso
error      → Falha na análise pelo LLM (passível de retry)
missing    → Não encontrada no filesystem (preservada no banco para histórico)
```

---

# 14. SQLite e Persistência

Tabelas do banco de dados (`data.db`):

- `schema_version`: Controle e versionamento do schema.
- `roots`: Raízes e caminhos monitorados.
- `entities`: Metadados das entidades, fingerprints e status.
- `files`: Arquivos pertencentes às entidades (sem armazenar conteúdo).
- `analyses`: Análises consolidadas pelo LLM, incluindo `tags_json`.
- `history`: Auditoria e histórico de alterações estruturais.

O banco migra suavemente colunas ausentes (ex: `tags_json`) sem perda de dados.

---

# 15. Provedores LLM

O acesso ao LLM é feito via contrato agnóstico `LLMProvider`:

- **OpenAI:** Modelos GPT (`gpt-4o-mini`, etc.).
- **OpenRouter:** Acesso unificado a DeepSeek (`deepseek/deepseek-v4-flash-0731`), Anthropic Claude, Meta Llama, etc.
- **Anthropic:** Claude API direta.
- **Ollama / LM Studio:** Modelos locais.
- **MockProvider:** Para testes automatizados sem chamadas externas de rede.

As chaves de API são injetadas via `.env` ou variáveis de ambiente do sistema (`api_key_env`).

---

# 16. Contrato de Entrada e Saída do LLM

### Entrada (Contexto Estruturado)
Payload contendo tipo da operação (`initial` ou `update`), manifesto, metadados de arquivos relevantes, assinaturas de código e análise anterior (em caso de atualização).

### Saída (JSON Estrito e Validado)
```json
{
  "name": "Nome representativo do projeto",
  "type": "tipo_semantico",
  "description": "Resumo conciso de 1 ou 2 frases.",
  "purpose": "Propósito prático ou problema central que o código resolve.",
  "languages": ["Python", "Rust"],
  "technologies": ["FastAPI", "Docker"],
  "tags": ["conceito_objetivo1", "conceito_objetivo2", "conceito_objetivo3"],
  "confidence": 1.0
}
```

O LLM não define hashes, contagem de linhas ou caminhos absolutos (responsabilidade exclusiva do Python).

---

# 17. Tipos Semânticos e Tags Conceituais

### Tipos Semânticos Sugeridos:
`application`, `library`, `utility`, `script`, `service`, `web`, `cli`, `automation`, `infrastructure`, `experiment`, `unknown`.

### Tags Semânticas de Domínio e Objetivo:
O campo `tags` gerado pelo LLM deve conter palavras-chave em minúsculas que resumam o **domínio, objetivo e funcionalidade central** do projeto (ex: editor de markdown → `["editor", "markdown", "texto"]`; controle de energia → `["energia", "shutdown", "remoto"]`).

---

# 18. Relatórios Markdown e Integração com Obsidian

Todos os relatórios são gerados no diretório `reports/` com prefixação por **dispositivo** (`device`), prontos para uso no **Obsidian**:

```
reports/
├── {device}-INDEX.md
└── projects/
    ├── {device}-projeto1.md
    ├── {device}-projeto2.md
    └── ...
```

### 18.1. Estrutura dos Arquivos (.md)

Todo relatório individual e o índice iniciam com:

1. **Frontmatter YAML:**
   ```yaml
   ---
   tags:
     - control_project
     - {tag_conceitual_1}
     - {tag_conceitual_2}
     - {tag_conceitual_3}
     - {tag_conceitual_4}
   Titulo: "{Nome do Projeto}"
   Data: {YYYY-MM-DD}
   Resumo: "{Resumo em uma linha}"
   ---
   ```
   *(A tag `control_project` é a base obrigatória; completada com até 4 tags conceituais de objetivo, totalizando no máximo 5 tags).*

2. **Bloco Obsidian TOC:**
   ```table-of-contents
   title: 
   style: nestedList # TOC style (nestedList|nestedOrderedList|inlineFirstLevel)
   includeLinks: true # Make headings clickable
   hideWhenEmpty: false # Hide TOC if no headings are found
   debugInConsole: false # Print debug info in Obsidian console
   ```

3. **Corpo do Relatório:**
   Visão geral, propósito detalhado, linguagens, frameworks/tecnologias e tabela de arquivos relevantes.

### 18.2. Catálogo Mestre (`{device}-INDEX.md`)
Agrupa o sumário geral e detalha as entidades divididas por raiz (`roots`) e por projetos individuais (`individual_projects`), classificadas por categorias semânticas.

---

# 19. Estrutura do Código

```
ctrl_prj/
├── cli/          # Comandos da CLI (scan, analyze, report, run)
├── config/       # Carregamento e validação de configurações e .env
├── scanner/      # Varredura do filesystem (roots e individual_projects)
├── discovery/    # Heurísticas de detecção de projetos e manifestos
├── fingerprint/  # Hashes SHA-256 e cálculo de deltas
├── analyzer/     # Extração estrutural leve e ContextBuilder
├── llm/          # Provedores LLM, contratos Pydantic e prompts
├── memory/       # SQLite models, repositórios e versionamento de schema
└── reporter/     # Gerador de relatórios Markdown, frontmatter, TOC e índice
```


