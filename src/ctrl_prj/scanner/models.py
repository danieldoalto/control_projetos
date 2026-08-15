"""Modelos de dados para o módulo de escaneamento de arquivos."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ScannedFile:
    """Representação dos metadados de um arquivo escaneado em uma entidade."""
    path: Path
    relative_path: str
    extension: str
    file_type: str  # 'code' ou 'context'
    is_code: bool
    is_context: bool
    size_bytes: int
    mtime: float
    language: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "path", self.path.resolve())
        # Normaliza barras para formato padrão '/'
        object.__setattr__(self, "relative_path", self.relative_path.replace("\\", "/"))
