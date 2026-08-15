"""Modelos de dados tipados para a camada de memória/persistência."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class RootRecord:
    """Registro de raiz monitorada."""
    id: Optional[int] = None
    path: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class EntityRecord:
    """Registro de entidade de projeto/script/coleção."""
    id: Optional[int] = None
    root_id: int = 0
    path: str = ""
    name: str = ""
    type: str = "project"  # project, collection, script
    status: str = "new"    # new, unchanged, changed, analyzed, error, missing
    fingerprint: Optional[str] = None
    last_scanned_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class FileRecord:
    """Registro de metadados de arquivo pertencente a uma entidade."""
    id: Optional[int] = None
    entity_id: int = 0
    relative_path: str = ""
    file_hash: str = ""
    size_bytes: int = 0
    lines_count: int = 0
    language: Optional[str] = None
    is_code: bool = False
    is_context: bool = False
    meta_json: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class AnalysisRecord:
    """Registro de análise de entidade gerada por LLM."""
    id: Optional[int] = None
    entity_id: int = 0
    name: str = ""
    type: str = "unknown"  # application, library, utility, script, service, web, cli, etc.
    description: str = ""
    purpose: Optional[str] = None
    languages_json: str = "[]"
    technologies_json: str = "[]"
    confidence: float = 1.0
    raw_response: Optional[str] = None
    entity_fingerprint: str = ""
    created_at: Optional[str] = None


@dataclass
class HistoryRecord:
    """Registro de auditoria/histórico de alterações detectadas."""
    id: Optional[int] = None
    entity_id: Optional[int] = None
    entity_path: str = ""
    event_type: str = "UNCHANGED"  # ADDED, MODIFIED, DELETED, UNCHANGED, MISSING
    fingerprint_before: Optional[str] = None
    fingerprint_after: Optional[str] = None
    details_json: Optional[str] = None
    created_at: Optional[str] = None
