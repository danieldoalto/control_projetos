"""Orquestrador do processo de Análise: integra SQLite, ContextBuilder, LLM e persistência."""

from dataclasses import dataclass, field
import json
import logging
from typing import Callable, List, Optional

from ctrl_prj.analyzer.context_builder import build_context
from ctrl_prj.config.settings import AppConfig
from ctrl_prj.llm.base import LLMProvider
from ctrl_prj.llm.contract import execute_analysis
from ctrl_prj.llm.factory import get_provider
from ctrl_prj.llm.schema import AnalysisResult
from ctrl_prj.memory import (
    AnalysisRecord,
    AnalysisRepository,
    Database,
    EntityRecord,
    EntityRepository,
    FileRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class EntityAnalysisSummary:
    """Resumo da análise de uma entidade individual."""
    entity_id: int
    name: str
    path: str
    semantic_type: str = "unknown"
    status: str = "analyzed"  # analyzed | error
    error_message: Optional[str] = None
    languages: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)


@dataclass
class AnalyzeResult:
    """Resultado consolidado da execução do comando Analyze."""
    total_pending: int = 0
    analyzed_count: int = 0
    error_count: int = 0
    already_analyzed_count: int = 0
    summaries: List[EntityAnalysisSummary] = field(default_factory=list)


# Tipo para callback opcional de progresso: (índice_atual, total, entidade, resultado_ou_none, erro_ou_none)
ProgressCallback = Callable[[int, int, EntityRecord, Optional[AnalysisResult], Optional[str]], None]


def run_analyze(
    config: AppConfig,
    db: Database,
    provider: Optional[LLMProvider] = None,
    on_progress: Optional[ProgressCallback] = None,
    force: bool = False,
) -> AnalyzeResult:
    """Executa o ciclo de análise LLM para todas as entidades pendentes (new / changed) ou todas se force=True.

    Args:
        config: Configuração da aplicação.
        db: Instância do banco SQLite.
        provider: Provedor de LLM opcional (se None, instanciado via Factory).
        on_progress: Callback opcional disparado após cada entidade processada.
        force: Se True, força reanálise de todas as entidades (mesmo já analisadas).

    Returns:
        AnalyzeResult consolidando métricas e sumário das análises.
    """
    result = AnalyzeResult()

    if provider is None:
        provider = get_provider(config)

    with db.get_connection() as conn:
        entity_repo = EntityRepository(conn)
        file_repo = FileRepository(conn)
        analysis_repo = AnalysisRepository(conn)

        all_entities = entity_repo.list_all()
        if force:
            pending_entities: List[EntityRecord] = [
                e for e in all_entities if e.status != "missing"
            ]
        else:
            pending_entities: List[EntityRecord] = [
                e for e in all_entities if e.status in ("new", "changed", "error")
            ]

        
        result.already_analyzed_count = len(all_entities) - len(pending_entities)

        result.total_pending = len(pending_entities)

        if not pending_entities:
            return result

        total = len(pending_entities)

        for index, entity in enumerate(pending_entities, start=1):
            entity_id = entity.id
            if entity_id is None:
                continue

            try:
                # 1. Recupera arquivos associados e análise anterior (se houver)
                files = file_repo.list_by_entity(entity_id)
                previous_analysis = analysis_repo.get_latest_by_entity(entity_id)

                # 2. Constrói contexto estruturado e otimizado
                context = build_context(
                    entity=entity,
                    files=files,
                    previous_analysis=previous_analysis,
                )

                # 3. Executa a interpretação pelo LLM com validação de contrato
                analysis_result: AnalysisResult = execute_analysis(
                    context=context,
                    provider=provider,
                )

                # 4. Salva o resultado consolidado no SQLite
                analysis_rec = AnalysisRecord(
                    entity_id=entity_id,
                    name=analysis_result.name,
                    type=analysis_result.type,
                    description=analysis_result.description,
                    purpose=analysis_result.purpose,
                    languages_json=json.dumps(analysis_result.languages, ensure_ascii=False),
                    technologies_json=json.dumps(analysis_result.technologies, ensure_ascii=False),
                    tags_json=json.dumps(analysis_result.tags, ensure_ascii=False),
                    confidence=analysis_result.confidence,
                    raw_response=analysis_result.raw_response,
                    entity_fingerprint=entity.fingerprint or "",
                )
                analysis_repo.create(analysis_rec)


                # 5. Atualiza o status da entidade para 'analyzed'
                entity_repo.update_status(entity_id, "analyzed")

                summary = EntityAnalysisSummary(
                    entity_id=entity_id,
                    name=analysis_result.name,
                    path=entity.path,
                    semantic_type=analysis_result.type,
                    status="analyzed",
                    languages=analysis_result.languages,
                    technologies=analysis_result.technologies,
                )
                result.summaries.append(summary)
                result.analyzed_count += 1

                if on_progress:
                    on_progress(index, total, entity, analysis_result, None)

            except Exception as exc:
                logger.error(
                    f"Erro ao analisar a entidade '{entity.name}' ({entity.path}): {exc}",
                    exc_info=True,
                )
                # Marca a entidade como erro para auditoria
                entity_repo.update_status(entity_id, "error")

                summary = EntityAnalysisSummary(
                    entity_id=entity_id,
                    name=entity.name,
                    path=entity.path,
                    semantic_type="unknown",
                    status="error",
                    error_message=str(exc),
                )
                result.summaries.append(summary)
                result.error_count += 1

                if on_progress:
                    on_progress(index, total, entity, None, str(exc))

    return result
