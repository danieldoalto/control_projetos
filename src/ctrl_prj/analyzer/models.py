"""Modelos de dados para análise estrutural de arquivos."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class FileStructure:
    """Metadados estruturais leves extraídos de um arquivo de código."""
    lines_count: int = 0
    imports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Indica se o arquivo não possui elementos estruturais identificados."""
        return not (self.imports or self.classes or self.functions or self.exports)

    def to_dict(self) -> Dict[str, Any]:
        """Converte a estrutura para um dicionário serializável."""
        return {
            "lines_count": self.lines_count,
            "imports": self.imports,
            "classes": self.classes,
            "functions": self.functions,
            "exports": self.exports,
        }
