"""Motor de descoberta e exploração do filesystem para ctrl_prj."""

from pathlib import Path
from typing import List, Optional, Set

from ctrl_prj.config.settings import DEFAULT_CODE_EXTENSIONS, DEFAULT_EXCLUSIONS
from ctrl_prj.discovery.heuristics import is_project_directory
from ctrl_prj.discovery.manifest import read_manifest
from ctrl_prj.discovery.models import DiscoveredEntity


def _is_excluded(path: Path, exclusion_set: Set[str]) -> bool:
    """Verifica se o arquivo ou diretório corresponde a uma exclusão."""
    name = path.name
    if name in exclusion_set:
        return True
    for excl in exclusion_set:
        if path.match(excl) or path.match(f"*/{excl}") or path.match(f"*/{excl}/*"):
            return True
    return False


class ProjectExplorer:
    """Explorador de filesystem para identificação de projetos e scripts."""

    def __init__(
        self,
        exclusions: Optional[List[str]] = None,
        code_extensions: Optional[List[str]] = None,
        follow_symlinks: bool = False,
    ):
        self.exclusions = set(exclusions or DEFAULT_EXCLUSIONS)
        self.code_extensions = set(code_extensions or DEFAULT_CODE_EXTENSIONS)
        self.follow_symlinks = follow_symlinks

    def discover_in_root(self, root_path: Path) -> List[DiscoveredEntity]:
        """Descobre entidades a partir de um diretório raiz.

        Args:
            root_path: Caminho da raiz a ser explorada.

        Returns:
            Lista de DiscoveredEntity encontradas sob esta raiz.
        """
        root_resolved = Path(root_path).expanduser().resolve()
        if not root_resolved.is_dir():
            return []

        discovered: List[DiscoveredEntity] = []
        self._explore_dir(
            current_dir=root_resolved,
            root_path=root_resolved,
            discovered=discovered,
            remaining_depth=None,
        )
        return discovered

    def discover_all(self, roots: List[Path]) -> List[DiscoveredEntity]:
        """Descobre entidades em todas as raízes configuradas.

        Args:
            roots: Lista de caminhos raízes.

        Returns:
            Lista consolidada de DiscoveredEntity ordenadas deterministicamente.
        """
        all_entities: List[DiscoveredEntity] = []
        seen_paths: Set[Path] = set()

        for root in roots:
            entities = self.discover_in_root(root)
            for entity in entities:
                if entity.path not in seen_paths:
                    seen_paths.add(entity.path)
                    all_entities.append(entity)

        all_entities.sort(key=lambda e: str(e.path))
        return all_entities

    def _explore_dir(
        self,
        current_dir: Path,
        root_path: Path,
        discovered: List[DiscoveredEntity],
        remaining_depth: Optional[int],
    ) -> None:
        """Explora recursivamente um diretório respeitando precedência e fronteiras."""
        if not self.follow_symlinks and current_dir.is_symlink():
            return

        if _is_excluded(current_dir, self.exclusions):
            return

        if remaining_depth is not None and remaining_depth <= 0:
            return

        # 1. Precedência: Checagem explícita (.ctrl_prj)
        manifest = read_manifest(current_dir)
        if manifest is not None:
            if manifest.type == "project":
                discovered.append(
                    DiscoveredEntity(
                        path=current_dir,
                        root_path=root_path,
                        type="project",
                        name=manifest.name or current_dir.name,
                        explicit=True,
                    )
                )
                # Regra de fronteira: subpastas pertencem ao projeto; encerra descida
                return

            if manifest.type == "script":
                discovered.append(
                    DiscoveredEntity(
                        path=current_dir,
                        root_path=root_path,
                        type="script",
                        name=manifest.name or current_dir.name,
                        explicit=True,
                    )
                )
                return

            if manifest.type == "collection":
                # Coleção: não adiciona como projeto, mas desce nos subdiretórios
                # até a profundidade especificada
                self._explore_subdirs(
                    current_dir=current_dir,
                    root_path=root_path,
                    discovered=discovered,
                    remaining_depth=manifest.depth,
                )
                return

        # 2. Heurística implícita
        if is_project_directory(current_dir, self.code_extensions):
            discovered.append(
                DiscoveredEntity(
                    path=current_dir,
                    root_path=root_path,
                    type="project",
                    name=current_dir.name,
                    explicit=False,
                )
            )
            # Regra de fronteira: subpastas pertencem ao projeto; encerra descida
            return

        # 3. Não é projeto nem explícito: desce para os subdiretórios
        next_depth = remaining_depth - 1 if remaining_depth is not None else None
        self._explore_subdirs(
            current_dir=current_dir,
            root_path=root_path,
            discovered=discovered,
            remaining_depth=next_depth,
        )

    def _explore_subdirs(
        self,
        current_dir: Path,
        root_path: Path,
        discovered: List[DiscoveredEntity],
        remaining_depth: Optional[int],
    ) -> None:
        """Itera e explora os subdiretórios de forma ordenada."""
        try:
            entries = sorted(current_dir.iterdir(), key=lambda p: p.name.lower())
        except (PermissionError, OSError):
            return

        for entry in entries:
            if entry.is_dir():
                self._explore_dir(
                    current_dir=entry,
                    root_path=root_path,
                    discovered=discovered,
                    remaining_depth=remaining_depth,
                )


def discover_entities(
    roots: List[Path],
    exclusions: Optional[List[str]] = None,
    code_extensions: Optional[List[str]] = None,
    follow_symlinks: bool = False,
) -> List[DiscoveredEntity]:
    """Helper funcional para executar descoberta em raízes."""
    explorer = ProjectExplorer(
        exclusions=exclusions,
        code_extensions=code_extensions,
        follow_symlinks=follow_symlinks,
    )
    return explorer.discover_all(roots)
