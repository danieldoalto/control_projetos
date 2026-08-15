"""Modelos de configuração e lógica de carregamento para ctrl_prj."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from ctrl_prj.config.exceptions import (
    ConfigError,
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)

DEFAULT_EXCLUSIONS: List[str] = [
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "target",
    "dist",
    "build",
    "coverage",
    ".cache",
]

DEFAULT_CODE_EXTENSIONS: List[str] = [
    ".py",
    ".rs",
    ".sh",
    ".bash",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
]

DEFAULT_CONTEXT_FILES: List[str] = [
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "package.json",
    "tsconfig.json",
    "Dockerfile",
    "*.yaml",
    "*.yml",
    "*.json",
    "*.toml",
    "*.sql",
    "Makefile",
]


def _expand_and_resolve_path(path_val: Union[str, Path]) -> Path:
    """Expande ~ e resolve caminhos para paths absolutos."""
    if isinstance(path_val, str):
        path_obj = Path(path_val.strip())
    else:
        path_obj = path_val
    return path_obj.expanduser().resolve()


class DatabaseConfig(BaseModel):
    """Configurações do banco de dados SQLite."""
    path: Path = Field(
        default_factory=lambda: _expand_and_resolve_path("~/.ctrl_prj/data.db"),
        description="Caminho do arquivo SQLite",
    )

    @field_validator("path", mode="before")
    @classmethod
    def _validate_path(cls, v: Any) -> Path:
        if v is None:
            return _expand_and_resolve_path("~/.ctrl_prj/data.db")
        return _expand_and_resolve_path(v)


class ScanConfig(BaseModel):
    """Configurações do scanner e discovery."""
    roots: List[Path] = Field(
        default_factory=list,
        description="Lista de diretórios raízes a escanear",
    )
    exclusions: List[str] = Field(
        default_factory=lambda: list(DEFAULT_EXCLUSIONS),
        description="Diretórios e padrões a ignorar",
    )
    code_extensions: List[str] = Field(
        default_factory=lambda: list(DEFAULT_CODE_EXTENSIONS),
        description="Extensões de arquivos de código",
    )
    context_files: List[str] = Field(
        default_factory=lambda: list(DEFAULT_CONTEXT_FILES),
        description="Padrões de arquivos de contexto",
    )
    follow_symlinks: bool = Field(
        default=False,
        description="Se deve seguir links simbólicos",
    )

    @field_validator("roots", mode="before")
    @classmethod
    def _validate_roots(cls, v: Any) -> List[Path]:
        if v is None:
            return []
        if isinstance(v, (str, Path)):
            return [_expand_and_resolve_path(v)]
        if isinstance(v, (list, tuple)):
            return [_expand_and_resolve_path(item) for item in v]
        raise ValueError(f"Formato inválido para roots: {v}")


class FingerprintConfig(BaseModel):
    """Configurações de cálculo de hash e fingerprint."""
    algorithm: str = Field(
        default="sha256",
        description="Algoritmo de hash para arquivos e entidades",
    )


class LLMConfig(BaseModel):
    """Configurações do provedor de LLM."""
    provider: str = Field(
        default="openai",
        description="Provedor de LLM (openai, anthropic, openrouter, ollama, lmstudio)",
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="Nome do modelo",
    )
    api_key_env: str = Field(
        default="OPENAI_API_KEY",
        description="Nome da variável de ambiente com a chave de API",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Temperatura de amostragem",
    )
    max_tokens: int = Field(
        default=2000,
        gt=0,
        description="Limite máximo de tokens de saída",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="URL base para APIs customizadas ou locais (Ollama, LM Studio)",
    )


class ReporterConfig(BaseModel):
    """Configurações de geração de relatórios."""
    output_dir: Path = Field(
        default_factory=lambda: _expand_and_resolve_path("reports"),
        description="Diretório onde os relatórios Markdown serão gerados",
    )

    @field_validator("output_dir", mode="before")
    @classmethod
    def _validate_output_dir(cls, v: Any) -> Path:
        if v is None:
            return _expand_and_resolve_path("reports")
        return _expand_and_resolve_path(v)


class AppConfig(BaseModel):
    """Configuração global da aplicação ctrl_prj."""
    scan: ScanConfig = Field(default_factory=ScanConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    fingerprint: FingerprintConfig = Field(default_factory=FingerprintConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    reporter: ReporterConfig = Field(default_factory=ReporterConfig)

    @model_validator(mode="before")
    @classmethod
    def _normalize_top_level(cls, data: Any) -> Any:
        """Normaliza chaves informadas na raiz para suas seções respectivas."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        # Normaliza scan e raízes se informadas no topo
        scan_dict = normalized.get("scan")
        if not isinstance(scan_dict, dict):
            scan_dict = {}

        if "roots" in normalized:
            scan_dict["roots"] = normalized.pop("roots")
        if "exclusions" in normalized:
            scan_dict["exclusions"] = normalized.pop("exclusions")
        if "code_extensions" in normalized:
            scan_dict["code_extensions"] = normalized.pop("code_extensions")
        if "context_files" in normalized:
            scan_dict["context_files"] = normalized.pop("context_files")
        if "follow_symlinks" in normalized:
            scan_dict["follow_symlinks"] = normalized.pop("follow_symlinks")

        if scan_dict:
            normalized["scan"] = scan_dict

        # Normaliza database se informado como string/Path no topo
        if "database" in normalized and isinstance(normalized["database"], (str, Path)):
            normalized["database"] = {"path": normalized["database"]}

        # Normaliza reporter se informado como string/Path no topo
        if "reporter" in normalized and isinstance(normalized["reporter"], (str, Path)):
            normalized["reporter"] = {"output_dir": normalized["reporter"]}

        return normalized

    @property
    def roots(self) -> List[Path]:
        """Atalho de conveniência para scan.roots."""
        return self.scan.roots

    @property
    def exclusions(self) -> List[str]:
        """Atalho de conveniência para scan.exclusions."""
        return self.scan.exclusions

    @property
    def database_path(self) -> Path:
        """Atalho de conveniência para database.path."""
        return self.database.path


def load_config(path: Optional[Union[str, Path]] = None) -> AppConfig:
    """Carrega e valida o arquivo de configuração YAML.

    Args:
        path: Caminho opcional para o arquivo config.yml. Se for None,
              tenta carregar 'config.yml' do diretório atual se existir,
              ou retorna a configuração default.

    Returns:
        AppConfig: Instância tipada e validada de configurações.

    Raises:
        ConfigNotFoundError: Se o arquivo explicitamente fornecido não existir.
        ConfigParseError: Se o arquivo YAML tiver sintaxe inválida.
        ConfigValidationError: Se o conteúdo não atender aos requisitos de tipos.
    """
    if path is None:
        default_file = Path("config.yml")
        if not default_file.exists():
            default_file = Path("config.yaml")

        if not default_file.exists():
            # Retorna configuração padrão válida
            return AppConfig()
        config_path = default_file
    else:
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigNotFoundError(
                f"Arquivo de configuração não encontrado: '{config_path}'"
            )

    try:
        content = config_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ConfigError(f"Erro ao ler arquivo de configuração '{config_path}': {exc}") from exc

    try:
        raw_data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ConfigParseError(
            f"Erro de sintaxe no YAML de configuração '{config_path}': {exc}"
        ) from exc

    if raw_data is None:
        return AppConfig()

    if not isinstance(raw_data, dict):
        raise ConfigValidationError(
            f"O conteúdo de '{config_path}' deve ser um mapeamento/dicionário YAML, recebeu {type(raw_data).__name__}."
        )

    try:
        return AppConfig.model_validate(raw_data)
    except Exception as exc:
        raise ConfigValidationError(
            f"Falha na validação das configurações em '{config_path}': {exc}"
        ) from exc
