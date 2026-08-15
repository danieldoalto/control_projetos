"""Heurísticas de identificação automática de projetos."""

from pathlib import Path
from typing import Optional, Set

from ctrl_prj.config.settings import DEFAULT_CODE_EXTENSIONS

# Arquivos marcadores inequívocos de projeto
PROJECT_MARKER_FILES: Set[str] = {
    "pyproject.toml",
    "cargo.toml",
    "package.json",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "tsconfig.json",
    "makefile",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "cmakelists.txt",
}

README_MARKERS: Set[str] = {
    "readme.md",
    "readme.txt",
    "readme.rst",
    "readme",
}


def is_project_directory(
    dir_path: Path,
    code_extensions: Optional[Set[str]] = None,
) -> bool:
    """Verifica se um diretório possui características heurísticas de um projeto.

    Args:
        dir_path: Caminho do diretório a avaliar.
        code_extensions: Conjunto de extensões de código reconhecidas (ex: {'.py', '.rs', ...}).

    Returns:
        bool: True se o diretório for heurísticamente classificado como projeto.
    """
    if not dir_path.is_dir():
        return False

    if code_extensions is None:
        code_exts = {ext.lower() for ext in DEFAULT_CODE_EXTENSIONS}
    else:
        code_exts = {ext.lower() for ext in code_extensions}

    has_readme = False
    has_code_file = False

    try:
        entries = list(dir_path.iterdir())
    except (PermissionError, OSError):
        return False

    for entry in entries:
        if entry.is_symlink():
            continue

        name_lower = entry.name.lower()

        # 1. Marcador explícito de projeto
        if entry.is_file() and name_lower in PROJECT_MARKER_FILES:
            return True

        if entry.is_file():
            if name_lower in README_MARKERS:
                has_readme = True

            ext = entry.suffix.lower()
            if ext in code_exts:
                has_code_file = True

    # 2. README acompanhado de arquivo de código no mesmo diretório
    if has_readme and has_code_file:
        return True

    # 3. Presença de arquivos de código reconhecidos no diretório
    if has_code_file:
        return True

    return False
