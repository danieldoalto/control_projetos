"""Cálculo determinístico de Fingerprint para entidades de projeto/script."""

from typing import List, Union

from ctrl_prj.fingerprint.hasher import hash_bytes
from ctrl_prj.fingerprint.models import HashedFile


def calculate_entity_fingerprint(
    files: List[HashedFile],
    algorithm: str = "sha256",
) -> str:
    """Calcula o fingerprint determinístico da entidade a partir de seus arquivos.

    Os arquivos são ordenados alfabeticamente por `relative_path`, garantindo
    que a ordem em que foram descobertos no disco não altere o fingerprint.

    Args:
        files: Lista de arquivos com hashes calculados.
        algorithm: Algoritmo de hash (padrão: sha256).

    Returns:
        String hexadecimal do fingerprint da entidade.
    """
    if not files:
        # Entidade sem arquivos relevantes
        return hash_bytes(b"", algorithm=algorithm)

    # Ordenação estrita pelo relative_path (determinismo)
    sorted_files = sorted(files, key=lambda f: f.relative_path)

    # Concatenação previsível: "relative_path:file_hash\n"
    lines = [f"{f.relative_path}:{f.file_hash}\n" for f in sorted_files]
    payload = "".join(lines).encode("utf-8")

    return hash_bytes(payload, algorithm=algorithm)
