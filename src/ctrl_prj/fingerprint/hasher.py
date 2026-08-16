from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, List, Union

from ctrl_prj.fingerprint.models import HashedFile

if TYPE_CHECKING:
    from ctrl_prj.scanner.models import ScannedFile


CHUNK_SIZE = 64 * 1024  # 64 KB


def hash_bytes(data: bytes, algorithm: str = "sha256") -> str:
    """Calcula o hash hexadecimal de um array de bytes."""
    h = hashlib.new(algorithm)
    h.update(data)
    return h.hexdigest()


def hash_file(file_path: Union[str, Path], algorithm: str = "sha256") -> str:
    """Calcula o hash de um arquivo lendo em blocos contínuos de bytes.

    Args:
        file_path: Caminho do arquivo a calcular o hash.
        algorithm: Algoritmo de hash suportado por hashlib (padrão: sha256).

    Returns:
        String hexadecimal do digest.
    """
    path_obj = Path(file_path)
    h = hashlib.new(algorithm)
    with path_obj.open("rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def hash_scanned_file(scanned_file: ScannedFile, algorithm: str = "sha256") -> HashedFile:
    """Calcula o hash de um ScannedFile e retorna um HashedFile."""
    f_hash = hash_file(scanned_file.path, algorithm=algorithm)
    return HashedFile.from_scanned_file(scanned_file, f_hash)


def hash_scanned_files(
    scanned_files: List[ScannedFile],
    algorithm: str = "sha256",
) -> List[HashedFile]:
    """Calcula o hash para uma lista de ScannedFiles."""
    return [hash_scanned_file(f, algorithm=algorithm) for f in scanned_files]
