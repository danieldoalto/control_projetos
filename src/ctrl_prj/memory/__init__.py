"""Módulo memory para persistência e recuperação no SQLite."""

from ctrl_prj.memory.database import Database
from ctrl_prj.memory.models import (
    AnalysisRecord,
    EntityRecord,
    FileRecord,
    HistoryRecord,
    RootRecord,
)
from ctrl_prj.memory.repository import (
    AnalysisRepository,
    EntityRepository,
    FileRepository,
    HistoryRepository,
    RootRepository,
)
from ctrl_prj.memory.schema import (
    SCHEMA_VERSION,
    get_schema_version,
    init_db,
)


class MemoryManager:
    """Orquestrador da camada de persistência e repositórios."""

    def __init__(self, db: Database):
        self.db = db

    def get_connection(self):
        """Retorna uma nova conexão com SQLite configurada."""
        return self.db.get_connection()

    def roots(self, conn) -> RootRepository:
        return RootRepository(conn)

    def entities(self, conn) -> EntityRepository:
        return EntityRepository(conn)

    def files(self, conn) -> FileRepository:
        return FileRepository(conn)

    def analyses(self, conn) -> AnalysisRepository:
        return AnalysisRepository(conn)

    def history(self, conn) -> HistoryRepository:
        return HistoryRepository(conn)


__all__ = [
    "Database",
    "MemoryManager",
    "RootRecord",
    "EntityRecord",
    "FileRecord",
    "AnalysisRecord",
    "HistoryRecord",
    "RootRepository",
    "EntityRepository",
    "FileRepository",
    "AnalysisRepository",
    "HistoryRepository",
    "SCHEMA_VERSION",
    "init_db",
    "get_schema_version",
]
