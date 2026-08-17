"""Leitor e parser do arquivo de manifesto explícito .ctrl_prj."""

from pathlib import Path
from typing import Optional

from ctrl_prj.discovery.models import Manifest

MANIFEST_FILENAME = ".ctrl_prj"


def read_manifest(dir_or_file_path: Path) -> Optional[Manifest]:
    """Lê e processa o arquivo .ctrl_prj de um diretório ou arquivo direto.

    Args:
        dir_or_file_path: Diretório contendo .ctrl_prj ou o próprio caminho do arquivo.

    Returns:
        Manifest ou None se o arquivo não existir ou não puder ser lido.
    """
    try:
        path = Path(dir_or_file_path)
        if path.is_dir():
            manifest_file = path / MANIFEST_FILENAME
        else:
            manifest_file = path

        if not manifest_file.is_file():
            return None

        content = manifest_file.read_text(encoding="utf-8")
    except Exception:
        return None

    data: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            data[key.strip().lower()] = val.strip()

    entity_type = data.get("type", "project").lower()
    if entity_type not in {"project", "collection", "script"}:
        entity_type = "project"

    name = data.get("name")
    
    depth = 1
    if "depth" in data:
        try:
            depth = max(1, int(data["depth"]))
        except ValueError:
            depth = 1

    return Manifest(
        type=entity_type,
        name=name if name else None,
        depth=depth,
    )
