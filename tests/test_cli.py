import pytest
from ctrl_prj.cli import main, build_parser


def test_cli_help(capsys):
    """Verifica se o CLI exibe ajuda quando chamado sem argumentos."""
    exit_code = main([])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ctrl_prj" in captured.out or "usage:" in captured.out


def test_cli_scan_default(capsys):
    """Verifica o comando scan sem arquivo de configuração personalizado."""
    exit_code = main(["scan"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Nenhuma raiz" in captured.out or "varredura" in captured.out.lower()


def test_cli_analyze(capsys):
    """Verifica o comando analyze."""
    exit_code = main(["analyze"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Executing 'analyze'" in captured.out


def test_cli_report(capsys):
    """Verifica o comando report."""
    exit_code = main(["report"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Executing 'report'" in captured.out


def test_cli_run(capsys):
    """Verifica o comando run."""
    exit_code = main(["run"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Running complete pipeline" in captured.out


def test_cli_invalid_config(capsys):
    """Verifica se a CLI lida amigavelmente com erro de arquivo de configuração inexistente."""
    exit_code = main(["-c", "/nao/existe/config.yml", "scan"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Erro de configuração" in captured.err
