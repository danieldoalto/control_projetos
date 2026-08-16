"""Modelos de dados para o módulo de fingerprinting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from ctrl_prj.scanner.models import ScannedFile



@dataclass(frozen=True)
class HashedFile:
    """Metadados de um arquivo com seu hash criptográfico calculado."""
    path: Path
    relative_path: str
    file_hash: str
    extension: str
    file_type: str  # 'code' ou 'context'
    is_code: bool
    is_context: bool
    size_bytes: int
    mtime: float
    language: Optional[str] = None

    @classmethod
    def from_scanned_file(cls, scanned_file: ScannedFile, file_hash: str) -> "HashedFile":
        """Cria um HashedFile a partir de um ScannedFile e seu hash calculado."""
        return cls(
            path=scanned_file.path,
            relative_path=scanned_file.relative_path,
            file_hash=file_hash,
            extension=scanned_file.extension,
            file_type=scanned_file.file_type,
            is_code=scanned_file.is_code,
            is_context=scanned_file.is_context,
            size_bytes=scanned_file.size_bytes,
            mtime=scanned_file.mtime,
            language=scanned_file.language,
        )
