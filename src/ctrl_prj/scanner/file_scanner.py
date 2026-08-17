"""Motor de varredura de arquivos dentro de entidades para ctrl_prj."""

import fnmatch
from pathlib import Path
from typing import List, Optional, Set, Tuple

from ctrl_prj.config.settings import (
    DEFAULT_CODE_EXTENSIONS,
    DEFAULT_CONTEXT_FILES,
    DEFAULT_EXCLUSIONS,
)
from ctrl_prj.scanner.models import ScannedFile

# Extensões explicitamente ignoradas (binários, mídia, compactados, artefatos de build)
IGNORED_EXTENSIONS: Set[str] = {
    # Imagens
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp", ".tiff",
    # Mídia
    ".mp4", ".mp3", ".wav", ".mov", ".avi", ".mkv", ".flac", ".ogg",
    # Compactados
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
    # Binários e bibliotecas compiladas
    ".exe", ".bin", ".so", ".dylib", ".dll", ".o", ".a", ".pyc", ".pyo", ".pyd", ".class",
    # Bancos de dados e caches
    ".db", ".sqlite", ".sqlite3",
    # Temporários
    ".tmp", ".temp", ".bak", ".swp",
}

# Nomes de arquivos ignorados
IGNORED_FILENAMES: Set[str] = {
    ".ds_store", "thumbs.db", "desktop.ini",
}

# Mapeamento de extensões/nomes para nomes amigáveis de linguagem
LANGUAGE_MAP = {
    ".py": "python",
    ".rs": "rust",
    ".sh": "bash",
    ".bash": "bash",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".sql": "sql",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".rst": "restructuredtext",
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "requirements.txt": "requirements",
}


def _classify_file(
    file_path: Path,
    code_exts: Set[str],
    context_patterns: List[str],
) -> Optional[Tuple[str, str, bool, bool]]:
    """Classifica um arquivo como código ou contexto e infere a linguagem.

    Returns:
        (extension, language, is_code, is_context) ou None se não for relevante.
    """
    filename = file_path.name
    filename_lower = filename.lower()
    suffix = file_path.suffix.lower()

    if filename_lower in IGNORED_FILENAMES:
        return None

    if suffix in IGNORED_EXTENSIONS:
        return None

    # 1. Verifica se é arquivo de código
    if suffix and suffix in code_exts:
        lang = LANGUAGE_MAP.get(suffix, suffix.lstrip("."))
        return (suffix, lang, True, False)

    # 2. Verifica se corresponde a um arquivo ou padrão de contexto
    for pattern in context_patterns:
        pattern_lower = pattern.lower()
        if fnmatch.fnmatch(filename_lower, pattern_lower):
            # Determina a linguagem a partir do mapeamento ou extensão
            if filename_lower in LANGUAGE_MAP:
                lang = LANGUAGE_MAP[filename_lower]
            elif suffix in LANGUAGE_MAP:
                lang = LANGUAGE_MAP[suffix]
            elif suffix:
                lang = suffix.lstrip(".")
            else:
                lang = "context"

            ext = suffix if suffix else filename
            return (ext, lang, False, True)

    return None


class FileScanner:
    """Scanner de arquivos relevantes dentro de uma entidade."""

    def __init__(
        self,
        exclusions: Optional[List[str]] = None,
        code_extensions: Optional[List[str]] = None,
        context_files: Optional[List[str]] = None,
        follow_symlinks: bool = False,
    ):
        self.exclusions = set(exclusions or DEFAULT_EXCLUSIONS)
        self.code_extensions = {ext.lower() for ext in (code_extensions or DEFAULT_CODE_EXTENSIONS)}
        self.context_files = list(context_files or DEFAULT_CONTEXT_FILES)
        self.follow_symlinks = follow_symlinks

    def scan_entity(self, entity_path: Path) -> List[ScannedFile]:
        """Varre o diretório da entidade e retorna todos os arquivos relevantes.

        Args:
            entity_path: Caminho da entidade (diretório ou arquivo de script).

        Returns:
            Lista de ScannedFile ordenados deterministicamente por caminho relativo.
        """
        resolved_path = Path(entity_path).expanduser().resolve()
        if not resolved_path.exists():
            return []

        # Caso seja um arquivo individual (ex: script único)
        if resolved_path.is_file():
            if not self.follow_symlinks and resolved_path.is_symlink():
                return []
            info = _classify_file(resolved_path, self.code_extensions, self.context_files)
            if info is None:
                return []
            ext, lang, is_code, is_context = info
            stat = resolved_path.stat()
            return [
                ScannedFile(
                    path=resolved_path,
                    relative_path=resolved_path.name,
                    extension=ext,
                    file_type="code" if is_code else "context",
                    is_code=is_code,
                    is_context=is_context,
                    size_bytes=stat.st_size,
                    mtime=stat.st_mtime,
                    language=lang,
                )
            ]

        # Caso seja um diretório de projeto
        scanned_files: List[ScannedFile] = []
        self._scan_dir(
            current_dir=resolved_path,
            entity_root=resolved_path,
            scanned_files=scanned_files,
        )

        scanned_files.sort(key=lambda f: f.relative_path)
        return scanned_files

    def _scan_dir(
        self,
        current_dir: Path,
        entity_root: Path,
        scanned_files: List[ScannedFile],
    ) -> None:
        """Percorre recursivamente diretórios ignorando pastas excluídas e symlinks."""
        try:
            entries = sorted(current_dir.iterdir(), key=lambda p: p.name.lower())
        except (PermissionError, OSError):
            return

        for entry in entries:
            try:
                if not self.follow_symlinks and entry.is_symlink():
                    continue

                if self._is_path_excluded(entry):
                    continue

                if entry.is_dir():
                    self._scan_dir(
                        current_dir=entry,
                        entity_root=entity_root,
                        scanned_files=scanned_files,
                    )
                elif entry.is_file():
                    info = _classify_file(entry, self.code_extensions, self.context_files)
                    if info is None:
                        continue

                    ext, lang, is_code, is_context = info
                    try:
                        stat = entry.stat()
                    except (PermissionError, OSError):
                        continue

                    rel_path = entry.relative_to(entity_root).as_posix()
                    scanned_files.append(
                        ScannedFile(
                            path=entry,
                            relative_path=rel_path,
                            extension=ext,
                            file_type="code" if is_code else "context",
                            is_code=is_code,
                            is_context=is_context,
                            size_bytes=stat.st_size,
                            mtime=stat.st_mtime,
                            language=lang,
                        )
                    )
            except (PermissionError, OSError):
                continue

    def _is_path_excluded(self, path: Path) -> bool:
        """Verifica se um arquivo ou diretório está na lista de exclusões."""
        try:
            name = path.name
            name_lower = name.lower()

            # Ambientes virtuais e pacotes instalados
            if name_lower in {"site-packages", "dist-packages", "node_modules", "__pycache__"}:
                return True
            try:
                if path.is_dir() and ((path / "pyvenv.cfg").is_file() or (path / "conda-meta").is_dir()):
                    return True
            except (PermissionError, OSError):
                return True  # Sem permissão de leitura, ignora o diretório

            if name in self.exclusions or name_lower in self.exclusions:
                return True
            for excl in self.exclusions:
                if fnmatch.fnmatch(name, excl) or fnmatch.fnmatch(name_lower, excl.lower()) or path.match(excl) or path.match(f"*/{excl}") or path.match(f"*/{excl}/*"):
                    return True
            return False
        except (PermissionError, OSError):
            return True



def scan_entity_files(
    entity_path: Path,
    exclusions: Optional[List[str]] = None,
    code_extensions: Optional[List[str]] = None,
    context_files: Optional[List[str]] = None,
    follow_symlinks: bool = False,
) -> List[ScannedFile]:
    """Função utilitária para varrer arquivos de uma entidade."""
    scanner = FileScanner(
        exclusions=exclusions,
        code_extensions=code_extensions,
        context_files=context_files,
        follow_symlinks=follow_symlinks,
    )
    return scanner.scan_entity(entity_path)
