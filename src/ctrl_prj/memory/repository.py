"""Repositórios para acesso e manipulação de dados no SQLite."""

import sqlite3
from typing import Any, Dict, List, Optional

from ctrl_prj.memory.models import (
    AnalysisRecord,
    EntityRecord,
    FileRecord,
    HistoryRecord,
    RootRecord,
)


class RootRepository:
    """Repositório para operações na tabela roots."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_or_create(self, path: str) -> RootRecord:
        """Obtém ou cria uma raiz monitorada pelo seu caminho."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, path, created_at, updated_at FROM roots WHERE path = ?", (path,))
        row = cursor.fetchone()
        if row:
            return RootRecord(
                id=row["id"],
                path=row["path"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        cursor.execute("INSERT INTO roots (path) VALUES (?)", (path,))
        self.conn.commit()
        root_id = cursor.lastrowid
        return self.get_by_id(root_id)  # type: ignore

    def get_by_id(self, root_id: int) -> Optional[RootRecord]:
        """Recupera uma raiz pelo seu identificador."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, path, created_at, updated_at FROM roots WHERE id = ?", (root_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return RootRecord(
            id=row["id"],
            path=row["path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_by_path(self, path: str) -> Optional[RootRecord]:
        """Recupera uma raiz pelo caminho."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, path, created_at, updated_at FROM roots WHERE path = ?", (path,))
        row = cursor.fetchone()
        if not row:
            return None
        return RootRecord(
            id=row["id"],
            path=row["path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_all(self) -> List[RootRecord]:
        """Lista todas as raízes monitoradas."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, path, created_at, updated_at FROM roots ORDER BY path ASC")
        return [
            RootRecord(
                id=row["id"],
                path=row["path"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in cursor.fetchall()
        ]

    def delete(self, root_id: int) -> bool:
        """Deleta uma raiz pelo ID (dispara CASCADE em entidades filhas)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM roots WHERE id = ?", (root_id,))
        self.conn.commit()
        return cursor.rowcount > 0


class EntityRepository:
    """Repositório para operações na tabela entities."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, entity: EntityRecord) -> EntityRecord:
        """Insere ou atualiza uma entidade pelo seu caminho absoluto."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO entities (root_id, path, name, type, status, fingerprint, last_scanned_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                root_id = excluded.root_id,
                name = excluded.name,
                type = excluded.type,
                status = excluded.status,
                fingerprint = excluded.fingerprint,
                last_scanned_at = excluded.last_scanned_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                entity.root_id,
                entity.path,
                entity.name,
                entity.type,
                entity.status,
                entity.fingerprint,
                entity.last_scanned_at,
            ),
        )
        self.conn.commit()
        return self.get_by_path(entity.path)  # type: ignore

    def get_by_id(self, entity_id: int) -> Optional[EntityRecord]:
        """Recupera uma entidade pelo ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, root_id, path, name, type, status, fingerprint,
                   last_scanned_at, created_at, updated_at
            FROM entities WHERE id = ?
            """,
            (entity_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return EntityRecord(
            id=row["id"],
            root_id=row["root_id"],
            path=row["path"],
            name=row["name"],
            type=row["type"],
            status=row["status"],
            fingerprint=row["fingerprint"],
            last_scanned_at=row["last_scanned_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_by_path(self, path: str) -> Optional[EntityRecord]:
        """Recupera uma entidade pelo seu caminho absoluto."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, root_id, path, name, type, status, fingerprint,
                   last_scanned_at, created_at, updated_at
            FROM entities WHERE path = ?
            """,
            (path,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return EntityRecord(
            id=row["id"],
            root_id=row["root_id"],
            path=row["path"],
            name=row["name"],
            type=row["type"],
            status=row["status"],
            fingerprint=row["fingerprint"],
            last_scanned_at=row["last_scanned_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_all(self) -> List[EntityRecord]:
        """Lista todas as entidades."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, root_id, path, name, type, status, fingerprint,
                   last_scanned_at, created_at, updated_at
            FROM entities ORDER BY path ASC
            """
        )
        return [
            EntityRecord(
                id=row["id"],
                root_id=row["root_id"],
                path=row["path"],
                name=row["name"],
                type=row["type"],
                status=row["status"],
                fingerprint=row["fingerprint"],
                last_scanned_at=row["last_scanned_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in cursor.fetchall()
        ]

    def list_by_status(self, status: str) -> List[EntityRecord]:
        """Lista entidades filtrando por status."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, root_id, path, name, type, status, fingerprint,
                   last_scanned_at, created_at, updated_at
            FROM entities WHERE status = ? ORDER BY path ASC
            """,
            (status,),
        )
        return [
            EntityRecord(
                id=row["id"],
                root_id=row["root_id"],
                path=row["path"],
                name=row["name"],
                type=row["type"],
                status=row["status"],
                fingerprint=row["fingerprint"],
                last_scanned_at=row["last_scanned_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in cursor.fetchall()
        ]

    def update_status(self, entity_id: int, status: str) -> bool:
        """Atualiza apenas o status de uma entidade."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE entities SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, entity_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def update_fingerprint(
        self,
        entity_id: int,
        fingerprint: str,
        status: str,
        last_scanned_at: Optional[str] = None,
    ) -> bool:
        """Atualiza o fingerprint, status e data do scan de uma entidade."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE entities
            SET fingerprint = ?,
                status = ?,
                last_scanned_at = COALESCE(?, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (fingerprint, status, last_scanned_at, entity_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def delete(self, entity_id: int) -> bool:
        """Deleta uma entidade pelo ID (dispara CASCADE em files e analyses)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
        self.conn.commit()
        return cursor.rowcount > 0


class FileRepository:
    """Repositório para operações na tabela files."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, file_rec: FileRecord) -> FileRecord:
        """Insere ou atualiza um arquivo pertencente a uma entidade."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO files (
                entity_id, relative_path, file_hash, size_bytes,
                lines_count, language, is_code, is_context, meta_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_id, relative_path) DO UPDATE SET
                file_hash = excluded.file_hash,
                size_bytes = excluded.size_bytes,
                lines_count = excluded.lines_count,
                language = excluded.language,
                is_code = excluded.is_code,
                is_context = excluded.is_context,
                meta_json = excluded.meta_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                file_rec.entity_id,
                file_rec.relative_path,
                file_rec.file_hash,
                file_rec.size_bytes,
                file_rec.lines_count,
                file_rec.language,
                1 if file_rec.is_code else 0,
                1 if file_rec.is_context else 0,
                file_rec.meta_json,
            ),
        )
        self.conn.commit()
        return self.get_by_entity_and_path(file_rec.entity_id, file_rec.relative_path)  # type: ignore

    def bulk_upsert(self, files: List[FileRecord]) -> None:
        """Executa upsert em lote para arquivos de uma entidade."""
        cursor = self.conn.cursor()
        for f in files:
            cursor.execute(
                """
                INSERT INTO files (
                    entity_id, relative_path, file_hash, size_bytes,
                    lines_count, language, is_code, is_context, meta_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id, relative_path) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    size_bytes = excluded.size_bytes,
                    lines_count = excluded.lines_count,
                    language = excluded.language,
                    is_code = excluded.is_code,
                    is_context = excluded.is_context,
                    meta_json = excluded.meta_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    f.entity_id,
                    f.relative_path,
                    f.file_hash,
                    f.size_bytes,
                    f.lines_count,
                    f.language,
                    1 if f.is_code else 0,
                    1 if f.is_context else 0,
                    f.meta_json,
                ),
            )
        self.conn.commit()

    def get_by_entity_and_path(self, entity_id: int, relative_path: str) -> Optional[FileRecord]:
        """Recupera um arquivo pela chave única (entity_id, relative_path)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, entity_id, relative_path, file_hash, size_bytes,
                   lines_count, language, is_code, is_context, meta_json, updated_at
            FROM files
            WHERE entity_id = ? AND relative_path = ?
            """,
            (entity_id, relative_path),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return FileRecord(
            id=row["id"],
            entity_id=row["entity_id"],
            relative_path=row["relative_path"],
            file_hash=row["file_hash"],
            size_bytes=row["size_bytes"],
            lines_count=row["lines_count"],
            language=row["language"],
            is_code=bool(row["is_code"]),
            is_context=bool(row["is_context"]),
            meta_json=row["meta_json"],
            updated_at=row["updated_at"],
        )

    def list_by_entity(self, entity_id: int) -> List[FileRecord]:
        """Lista todos os arquivos associados a uma entidade."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, entity_id, relative_path, file_hash, size_bytes,
                   lines_count, language, is_code, is_context, meta_json, updated_at
            FROM files
            WHERE entity_id = ?
            ORDER BY relative_path ASC
            """,
            (entity_id,),
        )
        return [
            FileRecord(
                id=row["id"],
                entity_id=row["entity_id"],
                relative_path=row["relative_path"],
                file_hash=row["file_hash"],
                size_bytes=row["size_bytes"],
                lines_count=row["lines_count"],
                language=row["language"],
                is_code=bool(row["is_code"]),
                is_context=bool(row["is_context"]),
                meta_json=row["meta_json"],
                updated_at=row["updated_at"],
            )
            for row in cursor.fetchall()
        ]

    def delete_missing_in_entity(self, entity_id: int, active_relative_paths: List[str]) -> int:
        """Remove arquivos de uma entidade que não estão mais presentes no scan."""
        cursor = self.conn.cursor()
        if not active_relative_paths:
            cursor.execute("DELETE FROM files WHERE entity_id = ?", (entity_id,))
        else:
            placeholders = ",".join("?" for _ in active_relative_paths)
            query = f"DELETE FROM files WHERE entity_id = ? AND relative_path NOT IN ({placeholders})"
            cursor.execute(query, [entity_id, *active_relative_paths])
        self.conn.commit()
        return cursor.rowcount


class AnalysisRepository:
    """Repositório para análises consolidadas de entidades."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, analysis: AnalysisRecord) -> AnalysisRecord:
        """Cria um novo registro de análise."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO analyses (
                entity_id, name, type, description, purpose,
                languages_json, technologies_json, tags_json, confidence,
                raw_response, entity_fingerprint
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis.entity_id,
                analysis.name,
                analysis.type,
                analysis.description,
                analysis.purpose,
                analysis.languages_json,
                analysis.technologies_json,
                analysis.tags_json,
                analysis.confidence,
                analysis.raw_response,
                analysis.entity_fingerprint,
            ),
        )
        self.conn.commit()
        analysis_id = cursor.lastrowid
        return self.get_by_id(analysis_id)  # type: ignore

    def get_by_id(self, analysis_id: int) -> Optional[AnalysisRecord]:
        """Recupera uma análise pelo ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, entity_id, name, type, description, purpose,
                   languages_json, technologies_json, tags_json, confidence,
                   raw_response, entity_fingerprint, created_at
            FROM analyses WHERE id = ?
            """,
            (analysis_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return AnalysisRecord(
            id=row["id"],
            entity_id=row["entity_id"],
            name=row["name"],
            type=row["type"],
            description=row["description"],
            purpose=row["purpose"],
            languages_json=row["languages_json"],
            technologies_json=row["technologies_json"],
            tags_json=row["tags_json"] if "tags_json" in row.keys() and row["tags_json"] else "[]",
            confidence=row["confidence"],
            raw_response=row["raw_response"],
            entity_fingerprint=row["entity_fingerprint"],
            created_at=row["created_at"],
        )

    def get_latest_by_entity(self, entity_id: int) -> Optional[AnalysisRecord]:
        """Recupera a análise mais recente de uma entidade."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, entity_id, name, type, description, purpose,
                   languages_json, technologies_json, tags_json, confidence,
                   raw_response, entity_fingerprint, created_at
            FROM analyses WHERE entity_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (entity_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return AnalysisRecord(
            id=row["id"],
            entity_id=row["entity_id"],
            name=row["name"],
            type=row["type"],
            description=row["description"],
            purpose=row["purpose"],
            languages_json=row["languages_json"],
            technologies_json=row["technologies_json"],
            tags_json=row["tags_json"] if "tags_json" in row.keys() and row["tags_json"] else "[]",
            confidence=row["confidence"],
            raw_response=row["raw_response"],
            entity_fingerprint=row["entity_fingerprint"],
            created_at=row["created_at"],
        )

    def list_by_entity(self, entity_id: int) -> List[AnalysisRecord]:
        """Lista todas as análises históricas de uma entidade."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, entity_id, name, type, description, purpose,
                   languages_json, technologies_json, tags_json, confidence,
                   raw_response, entity_fingerprint, created_at
            FROM analyses WHERE entity_id = ?
            ORDER BY id DESC
            """,
            (entity_id,),
        )
        return [
            AnalysisRecord(
                id=row["id"],
                entity_id=row["entity_id"],
                name=row["name"],
                type=row["type"],
                description=row["description"],
                purpose=row["purpose"],
                languages_json=row["languages_json"],
                technologies_json=row["technologies_json"],
                tags_json=row["tags_json"] if "tags_json" in row.keys() and row["tags_json"] else "[]",
                confidence=row["confidence"],
                raw_response=row["raw_response"],
                entity_fingerprint=row["entity_fingerprint"],
                created_at=row["created_at"],
            )
            for row in cursor.fetchall()
        ]



class HistoryRepository:
    """Repositório para eventos de histórico e auditoria."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, history: HistoryRecord) -> HistoryRecord:
        """Registra um novo evento no histórico."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO history (
                entity_id, entity_path, event_type,
                fingerprint_before, fingerprint_after, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                history.entity_id,
                history.entity_path,
                history.event_type,
                history.fingerprint_before,
                history.fingerprint_after,
                history.details_json,
            ),
        )
        self.conn.commit()
        hist_id = cursor.lastrowid
        return self.get_by_id(hist_id)  # type: ignore

    def get_by_id(self, history_id: int) -> Optional[HistoryRecord]:
        """Recupera um registro de histórico pelo ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, entity_id, entity_path, event_type,
                   fingerprint_before, fingerprint_after, details_json, created_at
            FROM history WHERE id = ?
            """,
            (history_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return HistoryRecord(
            id=row["id"],
            entity_id=row["entity_id"],
            entity_path=row["entity_path"],
            event_type=row["event_type"],
            fingerprint_before=row["fingerprint_before"],
            fingerprint_after=row["fingerprint_after"],
            details_json=row["details_json"],
            created_at=row["created_at"],
        )

    def list_by_entity(self, entity_id: int) -> List[HistoryRecord]:
        """Lista eventos de histórico de uma entidade."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, entity_id, entity_path, event_type,
                   fingerprint_before, fingerprint_after, details_json, created_at
            FROM history WHERE entity_id = ?
            ORDER BY id DESC
            """,
            (entity_id,),
        )
        return [
            HistoryRecord(
                id=row["id"],
                entity_id=row["entity_id"],
                entity_path=row["entity_path"],
                event_type=row["event_type"],
                fingerprint_before=row["fingerprint_before"],
                fingerprint_after=row["fingerprint_after"],
                details_json=row["details_json"],
                created_at=row["created_at"],
            )
            for row in cursor.fetchall()
        ]
