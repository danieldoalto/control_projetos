"""Orquestrador do processo de Scan: integra Discovery, FileScanner, Fingerprint e SQLite."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional, Set

from ctrl_prj.config.settings import AppConfig
from ctrl_prj.discovery import DiscoveredEntity, discover_entities
from ctrl_prj.discovery.manifest import read_manifest
from ctrl_prj.fingerprint.calculator import calculate_entity_fingerprint

from ctrl_prj.fingerprint.comparator import MacroStatus, compare_entity_state
from ctrl_prj.fingerprint.delta import FileDelta, compute_file_delta
from ctrl_prj.fingerprint.hasher import hash_scanned_files
from ctrl_prj.fingerprint.models import HashedFile

from ctrl_prj.memory import (
    Database,
    EntityRecord,
    EntityRepository,
    FileRecord,
    FileRepository,
    HistoryRecord,
    HistoryRepository,
    RootRecord,
    RootRepository,
)
from ctrl_prj.scanner.file_scanner import scan_entity_files


@dataclass
class EntityScanSummary:
    """Resumo do scan para uma entidade individual."""
    path: str
    name: str
    type: str
    status: str  # new, changed, unchanged, missing
    fingerprint: str
    files_count: int
    delta: Optional[FileDelta] = None


@dataclass
class ScanResult:
    """Resultado consolidado da execução do comando Scan."""
    roots_scanned: int = 0
    total_entities: int = 0
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    missing_count: int = 0
    total_files: int = 0
    entity_summaries: List[EntityScanSummary] = field(default_factory=list)

    @property
    def has_updates(self) -> bool:
        """Indica se houve entidades novas, modificadas ou ausentes."""
        return bool(self.new_count or self.changed_count or self.missing_count)


def _current_timestamp_iso() -> str:
    """Retorna timestamp UTC atual no formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def _process_entity(
    entity: DiscoveredEntity,
    root_rec: RootRecord,
    algorithm: str,
    exclusions: List[str],
    code_exts: List[str],
    context_files: List[str],
    follow_symlinks: bool,
    force: bool,
    entity_repo: EntityRepository,
    file_repo: FileRepository,
    history_repo: HistoryRepository,
    result: ScanResult,
) -> None:
    """Processa uma entidade descoberta: escaneia arquivos, calcula fingerprint e persiste no SQLite."""
    entity_path_str = str(entity.path)
    result.total_entities += 1

    # Escaneia arquivos relevantes
    scanned_files = scan_entity_files(
        entity_path=entity.path,
        exclusions=exclusions,
        code_extensions=code_exts,
        context_files=context_files,
        follow_symlinks=follow_symlinks,
    )

    # Calcula hashes e fingerprint da entidade
    hashed_files = hash_scanned_files(scanned_files, algorithm=algorithm)
    current_fp = calculate_entity_fingerprint(hashed_files, algorithm=algorithm)
    result.total_files += len(hashed_files)

    # Compara estado contra o banco
    macro_status = compare_entity_state(
        entity_path=entity.path,
        current_fingerprint=current_fp,
        entity_repo=entity_repo,
    )

    now_ts = _current_timestamp_iso()

    if macro_status == MacroStatus.NEW:
        result.new_count += 1
        saved_entity = entity_repo.upsert(
            EntityRecord(
                root_id=root_rec.id,  # type: ignore
                path=entity_path_str,
                name=entity.name,
                type=entity.type,
                status="new",
                fingerprint=current_fp,
                last_scanned_at=now_ts,
            )
        )

        # Insere todos os arquivos
        db_files = [
            FileRecord(
                entity_id=saved_entity.id,  # type: ignore
                relative_path=f.relative_path,
                file_hash=f.file_hash,
                size_bytes=f.size_bytes,
                language=f.language,
                is_code=f.is_code,
                is_context=f.is_context,
            )
            for f in hashed_files
        ]
        file_repo.bulk_upsert(db_files)

        # Registra histórico
        history_repo.create(
            HistoryRecord(
                entity_id=saved_entity.id,
                entity_path=entity_path_str,
                event_type="ADDED",
                fingerprint_before=None,
                fingerprint_after=current_fp,
                details_json=json.dumps({"files_count": len(hashed_files)}),
            )
        )

        result.entity_summaries.append(
            EntityScanSummary(
                path=entity_path_str,
                name=entity.name,
                type=entity.type,
                status="new",
                fingerprint=current_fp,
                files_count=len(hashed_files),
            )
        )

    elif macro_status == MacroStatus.CHANGED:
        result.changed_count += 1
        saved_entity = entity_repo.get_by_path(entity_path_str)
        prev_fp = saved_entity.fingerprint if saved_entity else None
        entity_id = saved_entity.id if saved_entity else 0

        # Calcula delta de arquivos
        prev_files = file_repo.list_by_entity(entity_id)
        delta = compute_file_delta(hashed_files, prev_files)

        # Atualiza entidade no banco
        entity_repo.upsert(
            EntityRecord(
                root_id=root_rec.id,  # type: ignore
                path=entity_path_str,
                name=entity.name,
                type=entity.type,
                status="changed",
                fingerprint=current_fp,
                last_scanned_at=now_ts,
            )
        )

        # Atualiza tabela de arquivos (upsert dos atuais e deleção dos ausentes)
        db_files = [
            FileRecord(
                entity_id=entity_id,
                relative_path=f.relative_path,
                file_hash=f.file_hash,
                size_bytes=f.size_bytes,
                language=f.language,
                is_code=f.is_code,
                is_context=f.is_context,
            )
            for f in hashed_files
        ]
        file_repo.bulk_upsert(db_files)
        active_rel_paths = [f.relative_path for f in hashed_files]
        file_repo.delete_missing_in_entity(entity_id, active_rel_paths)

        # Registra histórico
        history_repo.create(
            HistoryRecord(
                entity_id=entity_id,
                entity_path=entity_path_str,
                event_type="MODIFIED",
                fingerprint_before=prev_fp,
                fingerprint_after=current_fp,
                details_json=json.dumps(delta.summary_dict),
            )
        )

        result.entity_summaries.append(
            EntityScanSummary(
                path=entity_path_str,
                name=entity.name,
                type=entity.type,
                status="changed",
                fingerprint=current_fp,
                files_count=len(hashed_files),
                delta=delta,
            )
        )

    else:  # UNCHANGED
        result.unchanged_count += 1
        saved_entity = entity_repo.get_by_path(entity_path_str)
        if saved_entity and saved_entity.id:
            if force:
                # Sincroniza arquivos e purga arquivos excluídos
                db_files = [
                    FileRecord(
                        entity_id=saved_entity.id,
                        relative_path=f.relative_path,
                        file_hash=f.file_hash,
                        size_bytes=f.size_bytes,
                        language=f.language,
                        is_code=f.is_code,
                        is_context=f.is_context,
                    )
                    for f in hashed_files
                ]
                file_repo.bulk_upsert(db_files)
                active_rel_paths = [f.relative_path for f in hashed_files]
                file_repo.delete_missing_in_entity(saved_entity.id, active_rel_paths)

            # Atualiza data do último scan
            new_status = "changed" if force else saved_entity.status
            entity_repo.update_fingerprint(
                entity_id=saved_entity.id,
                fingerprint=current_fp,
                status=new_status,
                last_scanned_at=now_ts,
            )

        result.entity_summaries.append(
            EntityScanSummary(
                path=entity_path_str,
                name=entity.name,
                type=entity.type,
                status="unchanged",
                fingerprint=current_fp,
                files_count=len(hashed_files),
            )
        )


def run_scan(config: AppConfig, db: Database, force: bool = False) -> ScanResult:
    """Executa o ciclo completo de Scan no filesystem e persiste no SQLite.

    Args:
        config: Configurações da aplicação.
        db: Instância do banco SQLite.
        force: Se True, força a sincronização/deleção de arquivos no banco mesmo em entidades inalteradas.

    Returns:
        ScanResult com métricas e detalhes do scan.
    """
    result = ScanResult()
    roots = config.roots
    individual_projects = config.individual_projects

    if not roots and not individual_projects:
        return result

    algorithm = config.fingerprint.algorithm
    exclusions = config.exclusions
    code_exts = config.scan.code_extensions
    context_files = config.scan.context_files
    follow_symlinks = config.scan.follow_symlinks

    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        file_repo = FileRepository(conn)
        history_repo = HistoryRepository(conn)

        # 1. Processamento das Pastas Raízes (contêineres com múltiplos projetos)
        for root_path in roots:
            resolved_root = Path(root_path).expanduser().resolve()
            if not resolved_root.exists() or not resolved_root.is_dir():
                continue

            result.roots_scanned += 1
            root_rec = root_repo.get_or_create(str(resolved_root))

            # Descoberta de entidades na raiz
            discovered_entities: List[DiscoveredEntity] = discover_entities(
                roots=[resolved_root],
                exclusions=exclusions,
                code_extensions=code_exts,
                follow_symlinks=follow_symlinks,
            )

            discovered_paths_in_root: Set[str] = set()

            for entity in discovered_entities:
                discovered_paths_in_root.add(str(entity.path))
                _process_entity(
                    entity=entity,
                    root_rec=root_rec,
                    algorithm=algorithm,
                    exclusions=exclusions,
                    code_exts=code_exts,
                    context_files=context_files,
                    follow_symlinks=follow_symlinks,
                    force=force,
                    entity_repo=entity_repo,
                    file_repo=file_repo,
                    history_repo=history_repo,
                    result=result,
                )

            # Detecção de entidades MISSING para esta raiz
            db_entities_for_root = [
                e for e in entity_repo.list_all() if e.root_id == root_rec.id
            ]

            for db_ent in db_entities_for_root:
                if db_ent.path not in discovered_paths_in_root and db_ent.status != "missing":
                    result.missing_count += 1
                    entity_repo.update_status(db_ent.id, "missing")  # type: ignore

                    history_repo.create(
                        HistoryRecord(
                            entity_id=db_ent.id,
                            entity_path=db_ent.path,
                            event_type="MISSING",
                            fingerprint_before=db_ent.fingerprint,
                            fingerprint_after=None,
                            details_json=json.dumps({"reason": "not_found_on_filesystem"}),
                        )
                    )

                    result.entity_summaries.append(
                        EntityScanSummary(
                            path=db_ent.path,
                            name=db_ent.name,
                            type=db_ent.type,
                            status="missing",
                            fingerprint=db_ent.fingerprint or "",
                            files_count=0,
                        )
                    )

        # 2. Processamento dos Projetos Individuais Diretos
        for ind_path in individual_projects:
            resolved_indiv = Path(ind_path).expanduser().resolve()
            root_rec = root_repo.get_or_create(str(resolved_indiv))

            if not resolved_indiv.exists():
                existing = entity_repo.get_by_path(str(resolved_indiv))
                if existing and existing.id and existing.status != "missing":
                    result.missing_count += 1
                    entity_repo.update_status(existing.id, "missing")
                    history_repo.create(
                        HistoryRecord(
                            entity_id=existing.id,
                            entity_path=existing.path,
                            event_type="MISSING",
                            fingerprint_before=existing.fingerprint,
                            fingerprint_after=None,
                            details_json=json.dumps({"reason": "individual_project_not_found"}),
                        )
                    )
                    result.entity_summaries.append(
                        EntityScanSummary(
                            path=existing.path,
                            name=existing.name,
                            type=existing.type,
                            status="missing",
                            fingerprint=existing.fingerprint or "",
                            files_count=0,
                        )
                    )
                continue

            result.roots_scanned += 1
            manifest = read_manifest(resolved_indiv)
            if resolved_indiv.is_dir():
                entity_name = (manifest.name if manifest and manifest.name else resolved_indiv.name)
                entity_type = (manifest.type if manifest and manifest.type else "project")
            else:
                entity_name = (manifest.name if manifest and manifest.name else resolved_indiv.stem)
                entity_type = "script"

            entity = DiscoveredEntity(
                path=resolved_indiv,
                name=entity_name,
                type=entity_type,
                root_path=resolved_indiv,
            )

            _process_entity(
                entity=entity,
                root_rec=root_rec,
                algorithm=algorithm,
                exclusions=exclusions,
                code_exts=code_exts,
                context_files=context_files,
                follow_symlinks=follow_symlinks,
                force=force,
                entity_repo=entity_repo,
                file_repo=file_repo,
                history_repo=history_repo,
                result=result,
            )

    return result

