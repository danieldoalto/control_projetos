"""Gerenciador de conexão com o banco de dados SQLite."""

from pathlib import Path
import sqlite3
from typing import Optional, Union

from ctrl_prj.memory.schema import init_db


class Database:
    """Gerencia conexões e inicialização do banco SQLite."""

    def __init__(self, db_path: Union[str, Path] = ":memory:", auto_init: bool = True):
        self.raw_path = str(db_path)
        self.auto_init = auto_init
        self._memory_conn: Optional[sqlite3.Connection] = None

        if self.raw_path == ":memory:":
            self._is_memory = True
            self.db_path = ":memory:"
            # Mantém conexão única aberta para persistir dados em memória durante a vida do objeto
            self._memory_conn = sqlite3.connect(":memory:")
            self._memory_conn.row_factory = sqlite3.Row
            self._memory_conn.execute("PRAGMA foreign_keys = ON;")
        else:
            self._is_memory = False
            path_obj = Path(self.raw_path).expanduser().resolve()
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(path_obj)

        if self.auto_init:
            conn = self.get_connection()
            init_db(conn)
            if not self._is_memory:
                conn.close()

    def get_connection(self) -> sqlite3.Connection:
        """Cria ou retorna conexão configurada com o SQLite."""
        if self._is_memory and self._memory_conn is not None:
            return self._memory_conn

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def close(self) -> None:
        """Fecha conexão em memória se existir."""
        if self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None
