"""Construtor de contexto otimizado para o LLM."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ctrl_prj.analyzer.models import LLMContext
from ctrl_prj.analyzer.structural import analyze_file
from ctrl_prj.fingerprint.delta import FileDelta
from ctrl_prj.memory.models import AnalysisRecord, EntityRecord, FileRecord

DEFAULT_MAX_CHARS_PER_CONTEXT_FILE = 5000


def _read_truncated_text_file(file_path: Path, max_chars: int) -> Optional[str]:
    """Lê o conteúdo textual de um arquivo aplicando limite seguro de caracteres."""
    if not file_path.is_file():
        return None

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    if len(content) > max_chars:
        return content[:max_chars] + "\n... [conteúdo truncado para economia de tokens] ..."

    return content


def _format_previous_analysis(analysis: AnalysisRecord) -> Dict[str, Any]:
    """Formata o registro de análise anterior em um dicionário legível."""
    languages: List[str] = []
    technologies: List[str] = []

    try:
        languages = json.loads(analysis.languages_json) if analysis.languages_json else []
    except Exception:
        pass

    try:
        technologies = json.loads(analysis.technologies_json) if analysis.technologies_json else []
    except Exception:
        pass

    return {
        "name": analysis.name,
        "type": analysis.type,
        "description": analysis.description,
        "purpose": analysis.purpose,
        "languages": languages,
        "technologies": technologies,
        "confidence": analysis.confidence,
    }


def _format_changes(changes: Union[FileDelta, Dict[str, Any]]) -> Dict[str, Any]:
    """Formata o delta de alterações em um dicionário limpo."""
    if isinstance(changes, FileDelta):
        return {
            "added": [f.relative_path for f in changes.added],
            "modified": [f.relative_path for f in changes.modified],
            "deleted": [f.relative_path for f in changes.deleted],
            "summary": changes.summary_dict,
        }
    return changes


def build_context(
    entity: EntityRecord,
    files: List[FileRecord],
    previous_analysis: Optional[AnalysisRecord] = None,
    changes: Optional[Union[FileDelta, Dict[str, Any]]] = None,
    max_chars_per_context_file: int = DEFAULT_MAX_CHARS_PER_CONTEXT_FILE,
) -> LLMContext:
    """Constrói o contexto otimizado para o LLM Provider a partir da entidade e seus arquivos.

    Args:
        entity: Registro da entidade no SQLite.
        files: Lista de arquivos catalogados pertencentes à entidade.
        previous_analysis: Última análise realizada pelo LLM, se existente.
        changes: Resumo de deltas de arquivos se for uma atualização.
        max_chars_per_context_file: Limite máximo de caracteres para arquivos de contexto.

    Returns:
        LLMContext: Payload estruturado pronto para envio ao prompt do modelo.
    """
    entity_root = Path(entity.path).expanduser().resolve()

    # Define operação: se houver análise prévia, é um update
    operation = "update" if previous_analysis is not None else "initial"

    entity_info = {
        "id": entity.id,
        "name": entity.name,
        "type": entity.type,
        "path": entity.path,
        "status": entity.status,
        "fingerprint": entity.fingerprint,
    }

    file_structure_map: Dict[str, Dict[str, Any]] = {}
    context_files_content_map: Dict[str, str] = {}

    for f in sorted(files, key=lambda x: x.relative_path):
        if entity_root.is_file():
            physical_file_path = entity_root
        else:
            physical_file_path = entity_root / f.relative_path

        # 1. Arquivos de Código -> Análise Estrutural (Fatos)
        if f.is_code:
            structure = analyze_file(physical_file_path, language=f.language)
            file_structure_map[f.relative_path] = structure.to_dict()

        # 2. Arquivos de Contexto -> Conteúdo Textual com Limite de Caracteres
        elif f.is_context:
            text = _read_truncated_text_file(
                physical_file_path,
                max_chars=max_chars_per_context_file,
            )
            if text is not None:
                context_files_content_map[f.relative_path] = text

    formatted_prev_analysis = (
        _format_previous_analysis(previous_analysis) if previous_analysis is not None else None
    )

    formatted_changes = _format_changes(changes) if changes is not None else None

    return LLMContext(
        operation=operation,
        entity_info=entity_info,
        file_structure=file_structure_map,
        context_files_content=context_files_content_map,
        previous_analysis=formatted_prev_analysis,
        changes=formatted_changes,
    )
