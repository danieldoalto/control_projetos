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


def test_load_dotenv_integration(tmp_path, monkeypatch):
    """Verifica se variáveis do arquivo .env são lidas e inseridas no os.environ."""
    monkeypatch.chdir(tmp_path)
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        """
# Comentário
OPENROUTER_API_KEY="sk-or-v1-test-secret-token"
OUTRA_VARIAVEL=valor_sem_aspas
""",
        encoding="utf-8",
    )

    import os
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OUTRA_VARIAVEL", raising=False)

    load_config(None)

    assert os.getenv("OPENROUTER_API_KEY") == "sk-or-v1-test-secret-token"
    assert os.getenv("OUTRA_VARIAVEL") == "valor_sem_aspas"


def test_load_individual_projects_config(tmp_path):
    """Verifica se individual_projects é carregado e tem seus caminhos resolvidos."""
    config_file = tmp_path / "indiv_config.yml"
    config_file.write_text(
        """
scan:
  roots:
    - /tmp/raiz1
  individual_projects:
    - /tmp/projeto_avulso
    - ./relativo_indiv
""",
        encoding="utf-8",
    )
    cfg = load_config(config_file)
    assert len(cfg.roots) == 1
    assert len(cfg.individual_projects) == 2
    assert cfg.individual_projects[0] == Path("/tmp/projeto_avulso").resolve()
    assert cfg.individual_projects[1] == (tmp_path / "relativo_indiv").resolve()


def test_load_device_config(tmp_path):
    """Verifica carregamento de device/dispositivo no topo e em reporter."""
    # 1. No nível superior
    c1 = tmp_path / "c1.yml"
    c1.write_text("device: meu-note\n", encoding="utf-8")
    cfg1 = load_config(c1)
    assert cfg1.reporter.device == "meu-note"
    assert cfg1.device == "meu-note"

    # 2. Sob a seção reporter
    c2 = tmp_path / "c2.yml"
    c2.write_text("reporter:\n  device: meu-pc-gamer\n", encoding="utf-8")
    cfg2 = load_config(c2)
    assert cfg2.device == "meu-pc-gamer"


def test_load_logging_config(tmp_path):
    """Verifica carregamento e ancoragem relativa da seção logging."""
    cfg_file = tmp_path / "logging_config.yml"
    cfg_file.write_text(
        """
logging:
  level: DEBUG
  destination: both
  file_path: custom_logs/app.log
  max_size_mb: 5.5
  max_backups: 3
  compress: false
""",
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.logging.level == "DEBUG"
    assert cfg.log_level == "DEBUG"
    assert cfg.logging.destination == "both"
    assert cfg.log_destination == "both"
    assert cfg.logging.file_path == (tmp_path / "custom_logs" / "app.log").resolve()
    assert cfg.logging.max_size_mb == 5.5
    assert cfg.logging.max_backups == 3
    assert cfg.logging.compress is False


def test_load_traffic_log_config(tmp_path):
    """Verifica carregamento e aliases do nível de log de tráfego LLM."""
    from ctrl_prj.config.settings import LLMConfig
    import pytest
    from pydantic import ValidationError

    cfg1 = LLMConfig(traffic_log="completo")
    assert cfg1.traffic_log == "full"

    cfg2 = LLMConfig(traffic_log="basico")
    assert cfg2.traffic_log == "basic"

    cfg3 = LLMConfig(traffic_log="nenhum")
    assert cfg3.traffic_log == "none"

    with pytest.raises(ValidationError):
        LLMConfig(traffic_log="invalido_123")





