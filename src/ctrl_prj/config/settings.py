import os
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


def load_dotenv(dotenv_path: Optional[Union[str, Path]] = None) -> None:
    """Carrega variáveis de ambiente de um arquivo .env se existir."""
    if dotenv_path is None:
        target = Path(".env")
    else:
        target = Path(dotenv_path)

    if not target.is_file():
        return

    try:
        content = target.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


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


def _expand_path(path_val: Union[str, Path]) -> Path:
    """Expande ~ sem resolver caminhos relativos antecipadamente."""
    if isinstance(path_val, str):
        path_obj = Path(path_val.strip())
    else:
        path_obj = path_val
    return path_obj.expanduser()


class DatabaseConfig(BaseModel):
    """Configurações do banco de dados SQLite."""
    path: Path = Field(
        default_factory=lambda: _expand_path("~/.ctrl_prj/data.db").resolve(),
        description="Caminho do arquivo SQLite",
    )

    @field_validator("path", mode="before")
    @classmethod
    def _validate_path(cls, v: Any) -> Path:
        if v is None:
            return _expand_path("~/.ctrl_prj/data.db")
        return _expand_path(v)


class ScanConfig(BaseModel):
    """Configurações do scanner e discovery."""
    roots: List[Path] = Field(
        default_factory=list,
        description="Lista de diretórios raízes a escanear",
    )
    individual_projects: List[Path] = Field(
        default_factory=list,
        description="Lista de caminhos de projetos ou scripts individuais diretos",
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
            return [_expand_path(v)]
        if isinstance(v, (list, tuple)):
            return [_expand_path(item) for item in v]
        raise ValueError(f"Formato inválido para roots: {v}")

    @field_validator("individual_projects", mode="before")
    @classmethod
    def _validate_individual_projects(cls, v: Any) -> List[Path]:
        if v is None:
            return []
        if isinstance(v, (str, Path)):
            return [_expand_path(v)]
        if isinstance(v, (list, tuple)):
            return [_expand_path(item) for item in v]
        raise ValueError(f"Formato inválido para individual_projects: {v}")



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


import socket


def _default_device_name() -> str:
    """Retorna o hostname da máquina atual ou 'local' como fallback."""
    try:
        return socket.gethostname() or "local"
    except Exception:
        return "local"


class ReporterConfig(BaseModel):
    """Configurações de geração de relatórios."""
    output_dir: Path = Field(
        default_factory=lambda: _expand_path("reports").resolve(),
        description="Diretório onde os relatórios Markdown serão gerados",
    )
    device: str = Field(
        default_factory=_default_device_name,
        description="Nome ou identificador do dispositivo/computador",
    )

    @field_validator("output_dir", mode="before")
    @classmethod
    def _validate_output_dir(cls, v: Any) -> Path:
        if v is None:
            return _expand_path("reports")
        return _expand_path(v)

    @field_validator("device", mode="before")
    @classmethod
    def _validate_device(cls, v: Any) -> str:
        if v is None or not str(v).strip():
            return _default_device_name()
        return str(v).strip()


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
        if "individual_projects" in normalized:
            scan_dict["individual_projects"] = normalized.pop("individual_projects")
        elif "projects" in normalized:
            scan_dict["individual_projects"] = normalized.pop("projects")
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

        # Normaliza reporter e device se informados no topo
        reporter_dict = normalized.get("reporter")
        if not isinstance(reporter_dict, dict):
            if isinstance(reporter_dict, (str, Path)):
                reporter_dict = {"output_dir": reporter_dict}
            else:
                reporter_dict = {}

        for dev_key in ("device", "dispositivo", "Dispositivo", "device_name"):
            if dev_key in normalized:
                reporter_dict["device"] = normalized.pop(dev_key)

        if reporter_dict:
            normalized["reporter"] = reporter_dict

        return normalized

    @property
    def roots(self) -> List[Path]:
        """Atalho de conveniência para scan.roots."""
        return self.scan.roots

    @property
    def individual_projects(self) -> List[Path]:
        """Atalho de conveniência para scan.individual_projects."""
        return self.scan.individual_projects

    @property
    def device(self) -> str:
        """Atalho de conveniência para reporter.device."""
        return self.reporter.device


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
    # Carrega variáveis de ambiente do .env se existir
    load_dotenv()

    if path is None:
        found_config: Optional[Path] = None
        current = Path.cwd().resolve()
        for candidate_dir in [current, *current.parents]:
            for name in ("config.yml", "config.yaml"):
                candidate = candidate_dir / name
                if candidate.is_file():
                    found_config = candidate
                    break
            if found_config or (candidate_dir / ".git").exists():
                break

        if not found_config:
            # Retorna configuração padrão válida
            return AppConfig()
        config_path = found_config
        if (config_path.parent / ".env").is_file():
            load_dotenv(config_path.parent / ".env")
    else:
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigNotFoundError(
                f"Arquivo de configuração não encontrado: '{config_path}'"
            )
        # Tenta carregar .env da mesma pasta do arquivo de config se existir
        if (config_path.parent / ".env").is_file():
            load_dotenv(config_path.parent / ".env")



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
        cfg = AppConfig.model_validate(raw_data)
        base_dir = config_path.parent
        # Ancorar caminhos relativos ao diretório do arquivo de configuração
        if not cfg.database.path.is_absolute():
            cfg.database.path = (base_dir / cfg.database.path).resolve()
        if not cfg.reporter.output_dir.is_absolute():
            cfg.reporter.output_dir = (base_dir / cfg.reporter.output_dir).resolve()
        resolved_roots = []
        for r in cfg.scan.roots:
            if not r.is_absolute():
                resolved_roots.append((base_dir / r).resolve())
            else:
                resolved_roots.append(r)
        cfg.scan.roots = resolved_roots

        resolved_individuals = []
        for p in cfg.scan.individual_projects:
            if not p.is_absolute():
                resolved_individuals.append((base_dir / p).resolve())
            else:
                resolved_individuals.append(p)
        cfg.scan.individual_projects = resolved_individuals

        return cfg
    except Exception as exc:

        raise ConfigValidationError(
            f"Falha na validação das configurações em '{config_path}': {exc}"
        ) from exc

