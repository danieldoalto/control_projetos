"""Testes para a interface de linha de comando (CLI)."""

from pathlib import Path
import pytest
from ctrl_prj.cli import build_parser, main


@pytest.fixture
def mock_cli_config(tmp_path: Path):
    """Gera um arquivo de configuração isolado com provider mock para testes da CLI."""
    db_path = tmp_path / "cli_test.db"
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        f"""
database:
  path: "{db_path.as_posix()}"
llm:
  provider: "mock"
reporter:
  output_dir: "{(tmp_path / 'reports').as_posix()}"
roots:
  - "{tmp_path.as_posix()}"
""",
        encoding="utf-8",
    )
    return str(config_file)


def test_cli_help(capsys):
    """Verifica se o CLI exibe ajuda quando chamado sem argumentos."""
    exit_code = main([])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ctrl_prj" in captured.out or "usage:" in captured.out


def test_cli_scan_default(mock_cli_config, capsys):
    """Verifica o comando scan."""
    exit_code = main(["-c", mock_cli_config, "scan"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "varredura" in captured.out.lower() or "concluída" in captured.out.lower()


def test_cli_analyze(mock_cli_config, capsys):
    """Verifica o comando analyze."""
    exit_code = main(["-c", mock_cli_config, "analyze"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Buscando entidades" in captured.out or "Nenhuma entidade pendente" in captured.out


def test_cli_report(mock_cli_config, capsys):
    """Verifica o comando report."""
    exit_code = main(["-c", mock_cli_config, "report"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Gerando relatórios" in captured.out or "Índice consolidado" in captured.out


def test_cli_run(mock_cli_config, capsys):
    """Verifica o comando run."""
    exit_code = main(["-c", mock_cli_config, "run"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "FASE 1/3: SCAN" in captured.out
    assert "FASE 2/3: ANALYZE" in captured.out
    assert "FASE 3/3: REPORT" in captured.out


def test_cli_invalid_config(capsys):
    """Verifica se a CLI lida amigavelmente com erro de arquivo de configuração inexistente."""
    exit_code = main(["-c", "/nao/existe/config.yml", "scan"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Erro de configuração" in captured.err


def test_cli_force_flags(mock_cli_config, capsys):
    """Verifica se flags --force funcionam para scan, analyze e run."""
    assert main(["-c", mock_cli_config, "scan", "--force"]) == 0
    assert main(["-c", mock_cli_config, "analyze", "--force"]) == 0
    assert main(["-c", mock_cli_config, "run", "--force"]) == 0
    captured = capsys.readouterr()
    assert "FASE 1/3: SCAN" in captured.out


def test_cli_log_flags(mock_cli_config, tmp_path):
    """Verifica se as flags globais --log-level e --log-dest são aceitas e executadas."""
    log_file = tmp_path / "cli_test_exec.log"
    exit_code = main([
        "-c", mock_cli_config,
        "--log-level", "DEBUG",
        "--log-dest", "file",
        "scan",
    ])
    assert exit_code == 0



def test_cli_llm_traffic_flag(mock_cli_config):
    """Verifica se a flag global --llm-traffic é aceita e repassada à configuração."""
    exit_code = main([
        "-c", mock_cli_config,
        "--llm-traffic", "full",
        "scan",
    ])
    assert exit_code == 0



