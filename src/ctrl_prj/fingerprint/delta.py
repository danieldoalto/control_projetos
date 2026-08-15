"""Cálculo e representação de deltas de arquivos dentro de uma entidade."""

from dataclasses import dataclass, field
from typing import Dict, List

from ctrl_prj.fingerprint.models import HashedFile
from ctrl_prj.memory.models import FileRecord


@dataclass(frozen=True)
class FileDelta:
    """Deltas granulares de arquivos entre o estado no disco e o estado salvo no SQLite."""
    added: List[HashedFile] = field(default_factory=list)
    modified: List[HashedFile] = field(default_factory=list)
    deleted: List[FileRecord] = field(default_factory=list)
    unchanged: List[HashedFile] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Indica se houve qualquer adição, modificação ou exclusão."""
        return bool(self.added or self.modified or self.deleted)

    @property
    def summary_dict(self) -> Dict[str, int]:
        """Resumo numérico das alterações."""
        return {
            "added": len(self.added),
            "modified": len(self.modified),
            "deleted": len(self.deleted),
            "unchanged": len(self.unchanged),
        }


def compute_file_delta(
    current_files: List[HashedFile],
    previous_files: List[FileRecord],
) -> FileDelta:
    """Calcula a diferença entre os arquivos atuais no disco e os gravados no banco.

    Args:
        current_files: Lista de HashedFile escaneados do filesystem.
        previous_files: Lista de FileRecord persistidos anteriormente no SQLite.

    Returns:
        FileDelta: Objeto categorizado contendo listas de added, modified, deleted e unchanged.
    """
    curr_map: Dict[str, HashedFile] = {f.relative_path: f for f in current_files}
    prev_map: Dict[str, FileRecord] = {f.relative_path: f for f in previous_files}

    added: List[HashedFile] = []
    modified: List[HashedFile] = []
    deleted: List[FileRecord] = []
    unchanged: List[HashedFile] = []

    # Identifica arquivos novos, modificados e inalterados
    for rel_path, curr_file in curr_map.items():
        if rel_path not in prev_map:
            added.append(curr_file)
        else:
            prev_file = prev_map[rel_path]
            if curr_file.file_hash != prev_file.file_hash:
                modified.append(curr_file)
            else:
                unchanged.append(curr_file)

    # Identifica arquivos deletados do disco
    for rel_path, prev_file in prev_map.items():
        if rel_path not in curr_map:
            deleted.append(prev_file)

    # Ordena determinística por relative_path
    added.sort(key=lambda f: f.relative_path)
    modified.sort(key=lambda f: f.relative_path)
    deleted.sort(key=lambda f: f.relative_path)
    unchanged.sort(key=lambda f: f.relative_path)

    return FileDelta(
        added=added,
        modified=modified,
        deleted=deleted,
        unchanged=unchanged,
    )
