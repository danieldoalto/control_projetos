"""Comparação de estado macro de entidades contra a persistência SQLite."""

from enum import Enum
from pathlib import Path
from typing import Optional, Union

from ctrl_prj.memory.models import EntityRecord
from ctrl_prj.memory.repository import EntityRepository


class MacroStatus(str, Enum):
    """Status macro da entidade perante o estado salvo."""
    NEW = "new"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


def compare_entity_state(
    entity_path: Union[str, Path],
    current_fingerprint: str,
    entity_repo: EntityRepository,
) -> MacroStatus:
    """Determina o estado macro de uma entidade comparando com o SQLite.

    Args:
        entity_path: Caminho da entidade (será resolvido para absoluto).
        current_fingerprint: Fingerprint atual recém-calculado.
        entity_repo: Repositório de entidades do SQLite.

    Returns:
        MacroStatus: NEW, UNCHANGED ou CHANGED.
    """
    resolved_path = str(Path(entity_path).expanduser().resolve())
    db_entity: Optional[EntityRecord] = entity_repo.get_by_path(resolved_path)

    if db_entity is None:
        return MacroStatus.NEW

    if db_entity.fingerprint == current_fingerprint:
        return MacroStatus.UNCHANGED

    return MacroStatus.CHANGED
