"""Modelos de dados para o módulo de Discovery."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Manifest:
    """Representação estruturada do arquivo .ctrl_prj."""
    type: str = "project"  # project, collection, script
    name: Optional[str] = None
    depth: int = 1


@dataclass(frozen=True)
class DiscoveredEntity:
    """Entidade lógica descoberta no filesystem."""
    path: Path
    root_path: Path
    type: str  # project, collection, script
    name: str
    explicit: bool = False  # True se definida via .ctrl_prj, False se via heurística
    depth: Optional[int] = None

    def __post_init__(self):
        # Garante que os caminhos sejam sempre absolutos e resolvidos
        object.__setattr__(self, "path", self.path.resolve())
        object.__setattr__(self, "root_path", self.root_path.resolve())
