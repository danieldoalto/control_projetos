"""Gerador de relatórios Markdown a partir do estado SQLite."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Set, Tuple

from ctrl_prj.config.settings import AppConfig
from ctrl_prj.log import get_logger
from ctrl_prj.memory import (
    AnalysisRecord,
    AnalysisRepository,
    Database,
    EntityRecord,
    EntityRepository,
    FileRecord,
    FileRepository,
    RootRecord,
    RootRepository,
)

logger = get_logger(__name__)



@dataclass
class ReportResult:
    """Resultado consolidado da geração de relatórios."""
    total_entities: int = 0
    total_reports: int = 0
    output_dir: Path = field(default_factory=Path)
    index_path: Path = field(default_factory=Path)
    generated_files: List[Path] = field(default_factory=list)


def sanitize_filename(name: str) -> str:
    """Sanitiza um nome de entidade para uso seguro como nome de arquivo.

    Converte para minúsculas, substitui espaços e caracteres especiais por hífens.
    """
    # Remove acentos e caracteres não ASCII / especiais
    s = name.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s or "unnamed"


def _format_size(size_bytes: int) -> str:
    """Formata bytes em unidade legível (B, KB, MB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


TOC_BLOCK = """```table-of-contents
title: 
style: nestedList # TOC style (nestedList|nestedOrderedList|inlineFirstLevel)
includeLinks: true # Make headings clickable
hideWhenEmpty: false # Hide TOC if no headings are found
debugInConsole: false # Print debug info in Obsidian console
```"""


def _sanitize_tag(tag: str) -> str:
    """Normaliza uma tag para uso em frontmatter YAML."""
    cleaned = tag.strip().lower()
    cleaned = re.sub(r"[^\w\-_]", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned


def _build_entity_tags(
    entity: EntityRecord,
    analysis: Optional[AnalysisRecord],
) -> List[str]:
    """Constrói a lista de até 5 tags semânticas para a entidade, tendo 'control_project' como base obrigatória."""
    tags: List[str] = ["control_project"]
    candidates: List[str] = []

    # 1. Tags sugeridas pelo LLM
    if analysis and analysis.tags_json:
        try:
            llm_tags = json.loads(analysis.tags_json)
            if isinstance(llm_tags, list):
                candidates.extend(llm_tags)
        except Exception:
            pass

    # 2. Tecnologias
    if analysis and analysis.technologies_json:
        try:
            techs = json.loads(analysis.technologies_json)
            if isinstance(techs, list):
                candidates.extend(techs)
        except Exception:
            pass

    # 3. Linguagens
    if analysis and analysis.languages_json:
        try:
            langs = json.loads(analysis.languages_json)
            if isinstance(langs, list):
                candidates.extend(langs)
        except Exception:
            pass

    # 4. Tipo semântico ou tipo base
    if analysis and analysis.type and analysis.type != "unknown":
        candidates.append(analysis.type)
    elif entity.type:
        candidates.append(entity.type)

    for c in candidates:
        if len(tags) >= 5:
            break
        tag_clean = _sanitize_tag(str(c))
        if tag_clean and tag_clean not in tags:
            tags.append(tag_clean)

    return tags


def generate_entity_report(
    entity: EntityRecord,
    analysis: Optional[AnalysisRecord],
    files: List[FileRecord],
) -> str:
    """Gera o conteúdo Markdown para o relatório de uma entidade individual.

    Args:
        entity: Registro da entidade no SQLite.
        analysis: Última análise gerada por LLM (se houver).
        files: Lista de arquivos pertencentes à entidade.

    Returns:
        String formatada em Markdown com Frontmatter YAML e Obsidian TOC.
    """
    display_name = analysis.name if (analysis and analysis.name) else entity.name
    semantic_type = analysis.type if analysis else entity.type
    description = (
        analysis.description
        if (analysis and analysis.description)
        else "Nenhuma descrição gerada ainda (entidade pendente de análise)."
    )
    purpose = analysis.purpose if (analysis and analysis.purpose) else "Não informado."
    
    languages: List[str] = []
    technologies: List[str] = []

    if analysis:
        try:
            languages = json.loads(analysis.languages_json) if analysis.languages_json else []
        except Exception:
            languages = []

        try:
            technologies = json.loads(analysis.technologies_json) if analysis.technologies_json else []
        except Exception:
            technologies = []

    confidence_str = f"{int(analysis.confidence * 100)}%" if analysis else "N/A"
    last_updated = (
        analysis.created_at
        if (analysis and analysis.created_at)
        else (entity.updated_at or entity.created_at or "N/A")
    )

    tags = _build_entity_tags(entity, analysis)
    raw_date = analysis.created_at if (analysis and analysis.created_at) else (entity.updated_at or entity.created_at or "")
    date_str = raw_date[:10] if len(raw_date) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    clean_summary = description.replace("\n", " ").replace('"', "'").strip()
    clean_title = display_name.replace('"', "'").strip()

    lines: List[str] = [
        "---",
        "tags:",
        *[f"  - {t}" for t in tags],
        f"Titulo: {clean_title}",
        f"Data: {date_str}",
        f"Resumo: {clean_summary}",
        "---",
        "",
        TOC_BLOCK,
        "",
        f"# {display_name}",
        "",
        f"> {description}",
        "",
        "## 📋 Visão Geral",
        f"- **Tipo Semântico:** `{semantic_type}`",
        f"- **Classificação Original:** `{entity.type}`",
        f"- **Caminho no Filesystem:** `{entity.path}`",
        f"- **Status:** `{entity.status}`",
        f"- **Fingerprint:** `{entity.fingerprint or 'N/A'}`",
        f"- **Última Análise / Atualização:** `{last_updated}`",
        f"- **Confiança da Análise:** `{confidence_str}`",
        "",
        "## 🎯 Propósito",
        purpose,
        "",
        "## 🛠️ Tecnologias e Linguagens",
    ]


    # Seção de Linguagens
    if languages:
        lines.append("### Linguagens Identificadas")
        for lang in languages:
            lines.append(f"- {lang}")
    else:
        lines.append("### Linguagens")
        lines.append("_Nenhuma linguagem detectada explicitamente._")
    lines.append("")

    # Seção de Tecnologias
    if technologies:
        lines.append("### Frameworks & Tecnologias")
        for tech in technologies:
            lines.append(f"- {tech}")
    else:
        lines.append("### Frameworks & Tecnologias")
        lines.append("_Nenhum framework ou biblioteca chave identificada._")
    lines.append("")

    # Seção de Arquivos Relevantes
    lines.append(f"## 📁 Arquivos Relevantes ({len(files)})")
    if files:
        lines.append("| Arquivo | Classificação | Linhas | Tamanho |")
        lines.append("|---|---|---|---|")
        for f in sorted(files, key=lambda x: x.relative_path):
            file_type = "Código" if f.is_code else ("Contexto" if f.is_context else "Outro")
            lang_label = f" ({f.language})" if f.language else ""
            lines.append(
                f"| `{f.relative_path}` | {file_type}{lang_label} | {f.lines_count} | {_format_size(f.size_bytes)} |"
            )
    else:
        lines.append("_Nenhum arquivo catalogado para esta entidade._")

    lines.append("")
    return "\n".join(lines)


# Mapeamento para agrupamento amigável no índice
SEMANTIC_CATEGORIES: Dict[str, str] = {
    "application": "🚀 Applications & Services",
    "service": "🚀 Applications & Services",
    "web": "🌐 Web & Frontend",
    "cli": "💻 CLI & Utilities",
    "utility": "💻 CLI & Utilities",
    "library": "📦 Libraries & Packages",
    "script": "📜 Scripts & Automation",
    "automation": "📜 Scripts & Automation",
    "infrastructure": "🏗️ Infrastructure & DevOps",
    "experiment": "🧪 Experiments & Spikes",
    "unknown": "❓ Outros / Não Classificados",
}


def _render_category_tables(
    entries: List[Tuple[EntityRecord, Optional[AnalysisRecord], str]],
) -> List[str]:
    """Renderiza tabelas agrupadas por tipo semântico para uma lista de entradas."""
    lines: List[str] = []
    grouped: Dict[str, List[Tuple[EntityRecord, Optional[AnalysisRecord], str]]] = {}
    for entry in entries:
        _, analysis, _ = entry
        sem_type = (analysis.type.lower() if analysis and analysis.type else "unknown")
        category_header = SEMANTIC_CATEGORIES.get(sem_type, "❓ Outros / Não Classificados")
        grouped.setdefault(category_header, []).append(entry)

    for category in sorted(grouped.keys()):
        category_entries = grouped[category]
        lines.append(f"### {category} ({len(category_entries)})")
        lines.append("")
        lines.append("| Projeto | Tipo | Descrição | Linguagens | Tecnologias |")
        lines.append("|---|---|---|---|---|")

        for entity, analysis, rel_path in sorted(
            category_entries,
            key=lambda x: (x[1].name if x[1] and x[1].name else x[0].name).lower(),
        ):
            name = analysis.name if (analysis and analysis.name) else entity.name
            sem_type = analysis.type if (analysis and analysis.type) else entity.type
            desc = (
                analysis.description
                if (analysis and analysis.description)
                else "_Análise pendente_"
            )
            desc = desc.replace("\n", " ").replace("|", "/")

            langs = ""
            techs = ""
            if analysis:
                try:
                    langs_list = json.loads(analysis.languages_json) if analysis.languages_json else []
                    langs = ", ".join(langs_list)
                except Exception:
                    langs = ""

                try:
                    techs_list = json.loads(analysis.technologies_json) if analysis.technologies_json else []
                    techs = ", ".join(techs_list)
                except Exception:
                    techs = ""

            status_flag = " ⚠️ *(ausente)*" if entity.status == "missing" else ""
            lines.append(
                f"| [{name}]({rel_path}){status_flag} | `{sem_type}` | {desc} | {langs or '-'} | {techs or '-'} |"
            )

        lines.append("")
    return lines


def generate_index(
    entries: List[Tuple[EntityRecord, Optional[AnalysisRecord], str]],
    output_dir: Path,
    roots_map: Optional[Dict[int, str]] = None,
    config_roots: Optional[List[Path]] = None,
    config_individuals: Optional[List[Path]] = None,
    device_name: Optional[str] = None,
) -> str:
    """Gera o arquivo INDEX.md estruturado com sumário detalhado e divisões por raízes e projetos individuais.

    Args:
        entries: Lista de tuplas (EntityRecord, Optional[AnalysisRecord], relative_md_path).
        output_dir: Diretório raiz de saída dos relatórios.
        roots_map: Mapeamento opcional de id da raiz para seu caminho string.
        config_roots: Lista de raízes contêineres configuradas.
        config_individuals: Lista de projetos individuais configurados.
        device_name: Nome identificador do computador/dispositivo.

    Returns:
        String formatada do INDEX.md.
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total_entities = len(entries)
    analyzed_count = sum(1 for _, a, _ in entries if a is not None)
    pending_count = total_entities - analyzed_count

    roots_map = roots_map or {}
    config_roots_str = {str(r) for r in (config_roots or [])}
    config_indiv_str = {str(p) for p in (config_individuals or [])}

    # Separa entradas por origem (raízes contêineres vs projetos individuais)
    root_groups: Dict[str, List[Tuple[EntityRecord, Optional[AnalysisRecord], str]]] = {}
    individual_entries: List[Tuple[EntityRecord, Optional[AnalysisRecord], str]] = []

    for entry in entries:
        entity, _, _ = entry
        root_path = roots_map.get(entity.root_id, "")

        if (
            root_path in config_indiv_str
            or entity.path in config_indiv_str
            or (root_path and entity.path == root_path and root_path not in config_roots_str)
        ):
            individual_entries.append(entry)
        elif root_path:
            root_groups.setdefault(root_path, []).append(entry)
        else:
            root_groups.setdefault("Outras Origens", []).append(entry)

    dev_title = f" ({device_name})" if device_name else ""
    dev_sub = f" para o dispositivo **{device_name}**" if device_name else ""

    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    index_title = f"Catálogo de Projetos ({device_name}) — ctrl_prj" if device_name else "Catálogo de Projetos — ctrl_prj"
    index_summary = f"Catálogo consolidado e indexado de projetos do dispositivo {device_name}." if device_name else "Catálogo consolidado e indexado de projetos."

    clean_index_title = index_title.replace('"', "'").strip()
    clean_index_summary = index_summary.replace('"', "'").strip()

    lines: List[str] = [
        "---",
        "tags:",
        "  - control_project",
        "  - index",
        "  - catalog",
        f"Titulo: {clean_index_title}",
        f"Data: {now_date}",
        f"Resumo: {clean_index_summary}",
        "---",
        "",
        TOC_BLOCK,
        "",
        f"# 📚 Catálogo de Projetos{dev_title} — ctrl_prj",
        "",
        f"_Relatório consolidado gerado automaticamente{dev_sub} a partir do SQLite em **{now_str}**._",
        "",
        "## 📊 Sumário Geral",
        f"- **Total de Entidades:** {total_entities}",
        f"- **Analisadas:** {analyzed_count}",
        f"- **Pendentes / Sem Análise:** {pending_count}",
        "",
    ]


    # Sumário por Raiz Contêiner
    if root_groups:
        lines.append("### 📁 Raízes de Projetos (`roots`)")
        for r_path in sorted(root_groups.keys()):
            r_entries = root_groups[r_path]
            r_analyzed = sum(1 for _, a, _ in r_entries if a is not None)
            r_pending = len(r_entries) - r_analyzed
            lines.append(
                f"- **`{r_path}`**: {len(r_entries)} entidades ({r_analyzed} analisadas, {r_pending} pendentes)"
            )
        lines.append("")

    # Sumário por Projetos Individuais
    if individual_entries:
        lines.append("### 📦 Projetos Individuais (`individual_projects`)")
        for ind_entry in sorted(individual_entries, key=lambda x: x[0].path):
            ind_entity, ind_analysis, ind_link = ind_entry
            ind_status = "analisado" if ind_analysis else "pendente"
            lines.append(f"- **[{ind_entity.name}]({ind_link})** (`{ind_entity.path}`): {ind_status}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 🗂️ Entidades por Origem e Categoria")
    lines.append("")

    # Seções por cada Raiz Contêiner
    if root_groups:
        for r_path in sorted(root_groups.keys()):
            r_entries = root_groups[r_path]
            lines.append("---")
            lines.append("")
            lines.append(f"## 📁 Raiz: `{r_path}` ({len(r_entries)})")
            lines.append("")
            lines.extend(_render_category_tables(r_entries))

    # Seção de Projetos Individuais
    if individual_entries:
        lines.append("---")
        lines.append("")
        lines.append(f"## 📦 Projetos Individuais ({len(individual_entries)})")
        lines.append("")
        lines.extend(_render_category_tables(individual_entries))

    if not root_groups and not individual_entries and entries:
        lines.extend(_render_category_tables(entries))

    return "\n".join(lines)


def generate_reports(
    config: AppConfig,
    db: Database,
    output_dir: Optional[Path] = None,
) -> ReportResult:
    """Executa a geração completa dos relatórios Markdown a partir do SQLite.

    Args:
        config: Configuração da aplicação.
        db: Instância do banco SQLite.
        output_dir: Caminho customizado para a pasta de relatórios.

    Returns:
        ReportResult com estatísticas e lista de arquivos gerados.
    """
    target_dir = output_dir or config.reporter.output_dir
    target_dir = Path(target_dir).expanduser().resolve()
    logger.info(f"Iniciando geração de relatórios Markdown em: {target_dir}")

    projects_dir = target_dir / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    result = ReportResult(output_dir=target_dir)

    device_name = config.device
    device_slug = sanitize_filename(device_name) if device_name else "local"
    index_filename = f"{device_slug}-INDEX.md"

    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        analysis_repo = AnalysisRepository(conn)
        file_repo = FileRepository(conn)

        roots = root_repo.list_all()
        roots_map = {r.id: r.path for r in roots if r.id is not None}

        entities = entity_repo.list_all()
        result.total_entities = len(entities)

        if not entities:
            logger.info("Nenhuma entidade encontrada no banco para geração de relatórios.")
            # Gera índice vazio
            index_path = target_dir / index_filename
            index_content = generate_index(
                [],
                target_dir,
                roots_map=roots_map,
                config_roots=config.roots,
                config_individuals=config.individual_projects,
                device_name=device_name,
            )
            index_path.write_text(index_content, encoding="utf-8")
            result.index_path = index_path
            result.generated_files.append(index_path)
            return result

        used_filenames: Set[str] = set()
        index_entries: List[Tuple[EntityRecord, Optional[AnalysisRecord], str]] = []

        for entity in entities:
            entity_id = entity.id
            if entity_id is None:
                continue

            latest_analysis = analysis_repo.get_latest_by_entity(entity_id)
            files = file_repo.list_by_entity(entity_id)

            # Define nome de arquivo seguro e único com prefixo do dispositivo
            base_slug = sanitize_filename(entity.name)
            candidate_filename = f"{device_slug}-{base_slug}.md"

            # Se houver colisão de nomes em caminhos distintos, adiciona o ID da entidade
            if candidate_filename in used_filenames:
                candidate_filename = f"{device_slug}-{base_slug}_{entity_id}.md"

            used_filenames.add(candidate_filename)

            # Gera relatório individual da entidade
            report_md = generate_entity_report(entity, latest_analysis, files)
            file_path = projects_dir / candidate_filename
            file_path.write_text(report_md, encoding="utf-8")
            logger.debug(f"Relatório gerado: {file_path.name} ({len(files)} arquivos)")

            result.generated_files.append(file_path)
            result.total_reports += 1

            # Link relativo a partir do INDEX.md (projects/{device}-{slug}.md)
            rel_link = f"projects/{candidate_filename}"
            index_entries.append((entity, latest_analysis, rel_link))

        # Gera o INDEX.md com agrupamentos por origem
        index_path = target_dir / index_filename
        index_content = generate_index(
            index_entries,
            target_dir,
            roots_map=roots_map,
            config_roots=config.roots,
            config_individuals=config.individual_projects,
            device_name=device_name,
        )
        index_path.write_text(index_content, encoding="utf-8")
        result.index_path = index_path
        result.generated_files.append(index_path)

    logger.info(
        f"Geração de relatórios concluída: {result.total_reports} relatórios individuais em 'projects/' "
        f"e índice consolidado em '{result.index_path}'"
    )
    return result


