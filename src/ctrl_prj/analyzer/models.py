"""Modelos de dados para análise estrutural e construção de contexto para o LLM."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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


@dataclass
class LLMContext:
    """Contexto estruturado e otimizado preparado para envio ao LLM Provider."""
    operation: str  # 'initial' ou 'update'
    entity_info: Dict[str, Any]
    file_structure: Dict[str, Dict[str, Any]]
    context_files_content: Dict[str, str]
    previous_analysis: Optional[Dict[str, Any]] = None
    changes: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializa o contexto completo em formato de dicionário limpo."""
        return {
            "operation": self.operation,
            "entity": self.entity_info,
            "previous_analysis": self.previous_analysis,
            "changes": self.changes,
            "file_structure": self.file_structure,
            "context_files": self.context_files_content,
        }
