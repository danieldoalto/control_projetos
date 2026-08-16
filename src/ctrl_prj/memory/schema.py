"""Definição do schema e inicialização das tabelas no SQLite."""

import sqlite3
from typing import Optional

SCHEMA_VERSION = 1

CREATE_SCHEMA_SQL = """
-- Controle de versão do schema
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Raízes monitoradas
CREATE TABLE IF NOT EXISTS roots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Entidades descobertas (projetos, coleções, scripts)
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_id INTEGER NOT NULL,
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    fingerprint TEXT,
    last_scanned_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (root_id) REFERENCES roots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_root_id ON entities(root_id);
CREATE INDEX IF NOT EXISTS idx_entities_status ON entities(status);
CREATE INDEX IF NOT EXISTS idx_entities_path ON entities(path);

-- Arquivos pertencentes às entidades (sem armazenar conteúdo)
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    lines_count INTEGER DEFAULT 0,
    language TEXT,
    is_code INTEGER NOT NULL DEFAULT 0,
    is_context INTEGER NOT NULL DEFAULT 0,
    meta_json TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    UNIQUE (entity_id, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_files_entity_id ON files(entity_id);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash);

-- Análises consolidadas de entidades geradas por LLM
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT NOT NULL,
    purpose TEXT,
    languages_json TEXT,
    technologies_json TEXT,
    tags_json TEXT,
    confidence REAL DEFAULT 1.0,
    raw_response TEXT,
    entity_fingerprint TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analyses_entity_id ON analyses(entity_id);

-- Histórico de eventos e alterações
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER,
    entity_path TEXT NOT NULL,
    event_type TEXT NOT NULL,
    fingerprint_before TEXT,
    fingerprint_after TEXT,
    details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_history_entity_id ON history(entity_id);
CREATE INDEX IF NOT EXISTS idx_history_event_type ON history(event_type);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Inicializa o schema do banco de dados e registra a versão atual."""
    cursor = conn.cursor()
    cursor.executescript(CREATE_SCHEMA_SQL)

    # Migração suave de colunas para tabelas existentes
    cursor.execute("PRAGMA table_info(analyses)")
    columns = [col[1] for col in cursor.fetchall()]
    if "tags_json" not in columns:
        cursor.execute("ALTER TABLE analyses ADD COLUMN tags_json TEXT")

    # Verifica schema_version
    cursor.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    current_ver = row[0] if row and row[0] is not None else 0

    if current_ver < SCHEMA_VERSION:
        cursor.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
    conn.commit()



def get_schema_version(conn: sqlite3.Connection) -> Optional[int]:
    """Retorna a versão atual do schema."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None
