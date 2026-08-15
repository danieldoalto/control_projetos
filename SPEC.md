# 1. ESPECIFICAÇÃO GERAL — `ctrl_prj`

## 1.1. Identificação

**Nome:** `ctrl_prj`

**Objetivo:** catalogar, identificar e manter uma descrição atualizada de projetos e pequenos códigos existentes em diferentes locais do filesystem.

**Linguagens analisadas inicialmente:**

- Python
- Rust
- Bash
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

Nenhum projeto deve ser analisado novamente quando não houver alteração.

### Economia de tokens

O LLM deve receber somente o contexto necessário.

### Determinismo

Scanner, fingerprint e geração de relatórios devem ser determinísticos.

### Separação de responsabilidades

```
Scanner
    → coleta fatos

Analyzer
    → prepara contexto

LLM
    → interpreta

SQLite
    → memoriza

Reporter
    → apresenta
```

---

# 3. Arquitetura

```
                    ┌─────────────┐
                    │  config.yml │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    SCAN     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   SQLite    │
                    └──────┬──────┘
                           │
                    new / changed
                           │
                           ▼
                    ┌─────────────┐
                    │   ANALYZE   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ LLM Provider│
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   SQLite    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   REPORT    │
                    └──────┬──────┘
                           │
                           ▼
                       Markdown
```

---

# 4. CLI

Comandos obrigatórios:

```
ctrl_prj scan
ctrl_prj analyze
ctrl_prj report
ctrl_prj run
```

### `scan`

Descobre e atualiza o estado do filesystem.

Não utiliza LLM.

### `analyze`

Analisa entidades novas ou modificadas.

Utiliza o provider LLM configurado.

### `report`

Gera os relatórios Markdown.

Não utiliza LLM.

### `run`

Executa:

```
scan → analyze → report
```

---

# 5. Roots

Podem existir múltiplas raízes:

```
scan:
  roots:
    - ~/projects
    - ~/project2
    - ~/scripts
```

As raízes são independentes.

---

# 6. `.ctrl_prj`

Arquivo opcional presente em qualquer diretório que necessite de classificação explícita.

Formato:

```
type=project
```

ou:

```
type=collection
depth=1
```

ou:

```
type=script
name=Meu script
```

Tipos:

```
project
collection
script
```

Configuração explícita tem precedência sobre heurística.

---

# 7. Descoberta

Quando não existe `.ctrl_prj`, o scanner utiliza heurísticas simples.

Indicadores de projeto incluem:

```
pyproject.toml
Cargo.toml
package.json
README.md
código reconhecido
```

Uma entidade identificada engloba sua árvore interna.

Por exemplo:

```
project/
├── src/
├── tests/
└── docs/
```

é uma única entidade.

---

# 8. Arquivos suportados

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

### Arquivos de contexto

Exemplos:

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

A lista deve ser configurável.

---

# 9. Exclusões

Por padrão:

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
```

Também serão ignorados:

- binários;
- imagens;
- vídeos;
- arquivos compactados;
- temporários.

Symlinks não serão seguidos na V1.

---

# 10. Análise estrutural local

O Python deve extrair informações simples.

Exemplo:

```
arquivo
linguagem
tamanho
linhas
imports
classes
funções
exports
```

A análise deve ser leve.

**Não construir um analisador estático complexo.**

---

# 11. Fingerprint

Cada arquivo relevante recebe hash.

Por padrão:

```
SHA-256
```

O fingerprint da entidade é calculado deterministicamente usando:

```
relative_path + file_hash
```

de todos os arquivos relevantes, ordenados.

---

# 12. Incrementalidade

O sistema identifica:

```
UNCHANGED
ADDED
MODIFIED
DELETED
```

Se o fingerprint não mudou:

```
não chama LLM
```

Se mudou:

```
compara hashes individuais
```

Somente arquivos relevantes alterados precisam ser reconsiderados pelo Analyzer.

---

# 13. Estados

As entidades podem assumir:

```
new
unchanged
changed
analyzed
error
missing
```

`missing` significa que a entidade anteriormente conhecida não foi encontrada no filesystem.

Ela não deve ser apagada do banco.

---

# 14. SQLite

Tabelas V1:

```
roots
entities
files
analyses
history
```

Não armazenar o conteúdo dos arquivos.

Não armazenar `file_analyses` permanentemente na V1.

---

# 15. LLM

O LLM deve ser acessado através de uma abstração:

```
LLMProvider
```

Possíveis providers:

```
OpenAI
Anthropic
OpenRouter
Ollama
LM Studio
```

O restante da aplicação não deve depender diretamente de nenhum deles.

---

# 16. Entrada do LLM

A entrada será estruturada e conterá, conforme o caso:

```
entity
metadata
structure
files
changes
previous_analysis
```

Primeira análise:

```
operation = initial
```

Atualização:

```
operation = update
```

---

# 17. Saída do LLM

Formato estruturado:

```
{
  "name": "...",
  "type": "...",
  "description": "...",
  "purpose": "...",
  "languages": [],
  "technologies": [],
  "confidence": 0.0
}
```

O LLM não define:

- caminho;
- hashes;
- datas;
- estado;
- quantidade de arquivos.

Esses dados pertencem ao Python.

---

# 18. Tipos semânticos do LLM

Sugestão:

```
application
library
utility
script
service
web
cli
automation
infrastructure
experiment
unknown
```

Isso permite relatórios consistentes.

---

# 19. Atualização

O LLM sempre retorna o **estado atual completo**.

Não retorna apenas um delta.

```
análise anterior
+
alterações
+
contexto atual
        ↓
LLM
        ↓
nova análise completa
```

---

# 20. Configuração

Arquivo central:

```
config.yml
```

Deve controlar:

- roots;
- exclusões;
- linguagens;
- hash;
- limites;
- SQLite;
- providers;
- modelos;
- prompts;
- relatórios.

API keys devem ser obtidas por variável de ambiente.

---

# 21. Relatórios

Saída:

```
reports/
├── INDEX.md
└── projects/
    ├── projeto1.md
    ├── projeto2.md
    └── ...
```

O relatório é derivado do SQLite.

O Markdown pode ser apagado e recriado sem perda de informação.

---

# 22. Estrutura de código

A implementação deve ser modular:

```
ctrl_prj/
├── cli
├── config
├── scanner
├── discovery
├── fingerprint
├── analyzer
├── llm
├── memory
└── reporter
```

A estrutura física exata pode ser refinada durante implementação.

