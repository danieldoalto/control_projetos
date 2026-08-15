from pathlib import Path
import pytest

from ctrl_prj.config import (
    AppConfig,
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    load_config,
)


def test_default_config_when_no_file(tmp_path, monkeypatch):
    """Verifica se valores default são aplicados quando nenhum arquivo existe."""
    monkeypatch.chdir(tmp_path)
    config = load_config(None)

    assert isinstance(config, AppConfig)
    assert config.roots == []
    assert ".git" in config.exclusions
    assert ".venv" in config.exclusions
    assert config.database.path == Path("~/.ctrl_prj/data.db").expanduser().resolve()
    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-4o-mini"
    assert config.llm.temperature == 0.0
    assert config.fingerprint.algorithm == "sha256"


def test_load_valid_config(tmp_path):
    """Verifica o carregamento correto de um arquivo YAML válido com expansão de caminhos."""
    config_file = tmp_path / "custom_config.yml"
    config_file.write_text(
        """
scan:
  roots:
    - ~/projetos_teste
    - /tmp/outro_projeto
  exclusions:
    - .git
    - build
database:
  path: ~/minhas_bases/ctrl.db
llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  api_key_env: ANTHROPIC_API_KEY
  temperature: 0.2
  max_tokens: 1500
reporter:
  output_dir: ~/meus_relatorios
""",
        encoding="utf-8",
    )

    cfg = load_config(config_file)

    assert len(cfg.roots) == 2
    assert cfg.roots[0] == Path("~/projetos_teste").expanduser().resolve()
    assert cfg.roots[1] == Path("/tmp/outro_projeto").resolve()
    assert cfg.exclusions == [".git", "build"]
    assert cfg.database.path == Path("~/minhas_bases/ctrl.db").expanduser().resolve()
    assert cfg.llm.provider == "anthropic"
    assert cfg.llm.model == "claude-3-5-sonnet-20241022"
    assert cfg.llm.temperature == 0.2
    assert cfg.llm.max_tokens == 1500
    assert cfg.reporter.output_dir == Path("~/meus_relatorios").expanduser().resolve()


def test_load_flattened_style_yaml(tmp_path, monkeypatch):
    """Verifica compatibilidade com chaves declaradas no nível raiz."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "flat_config.yml"
    config_file.write_text(
        """
roots:
  - ~/meu_codigo
database: ~/.ctrl_prj/custom.db
reporter: ./custom_reports
""",
        encoding="utf-8",
    )

    cfg = load_config(config_file)
    assert len(cfg.roots) == 1
    assert cfg.roots[0] == Path("~/meu_codigo").expanduser().resolve()
    assert cfg.database_path == Path("~/.ctrl_prj/custom.db").expanduser().resolve()
    assert cfg.reporter.output_dir == (tmp_path / "custom_reports").resolve()


def test_load_non_existent_file():
    """Verifica se erro específico é levantado quando arquivo explicitamente fornecido não existe."""
    with pytest.raises(ConfigNotFoundError) as exc_info:
        load_config("/caminho/completamente/inexistente/config.yml")
    assert "não encontrado" in str(exc_info.value)


def test_load_malformed_yaml(tmp_path):
    """Verifica se erro de sintaxe YAML é capturado e tratado."""
    bad_yaml = tmp_path / "bad.yml"
    bad_yaml.write_text("scan: [qualquer coisa quebrada: {", encoding="utf-8")

    with pytest.raises(ConfigParseError) as exc_info:
        load_config(bad_yaml)
    assert "Erro de sintaxe" in str(exc_info.value)


def test_load_invalid_content_type(tmp_path):
    """Verifica se erro de validação ocorre se o YAML não for um dicionário."""
    invalid_yaml = tmp_path / "invalid.yml"
    invalid_yaml.write_text("- item1\n- item2\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(invalid_yaml)
    assert "deve ser um mapeamento/dicionário" in str(exc_info.value)


def test_load_invalid_temperature_range(tmp_path):
    """Verifica se validações numéricas (como temperature fora de range) falham adequadamente."""
    invalid_yaml = tmp_path / "invalid_temp.yml"
    invalid_yaml.write_text(
        """
llm:
  temperature: 5.0
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(invalid_yaml)
    assert "Falha na validação" in str(exc_info.value)


def test_example_config_file_validity():
    """Garante que o arquivo config.example.yml do repositório é válido e parseável."""
    example_path = Path("config.example.yml")
    assert example_path.exists(), "config.example.yml deve existir na raiz"
    cfg = load_config(example_path)
    assert isinstance(cfg, AppConfig)
    assert len(cfg.roots) == 2
    assert cfg.llm.provider == "openai"
