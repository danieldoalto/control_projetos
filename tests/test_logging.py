"""Testes unitários e de integração para o módulo de log."""

import gzip
import logging
from pathlib import Path
import pytest
from pydantic import ValidationError

from ctrl_prj.config import LoggingConfig
from ctrl_prj.log import (
    CompressedRotatingFileHandler,
    get_logger,
    reset_logging,
    setup_logging,
)


def test_logging_config_defaults():
    """Verifica os valores padrão da configuração de log."""
    cfg = LoggingConfig()
    assert cfg.level == "INFO"
    assert cfg.destination == "console"
    assert cfg.file_path == Path("logs/ctrl_prj.log")
    assert cfg.max_size_mb == 10.0
    assert cfg.max_backups == 5
    assert cfg.compress is True
    assert "%(asctime)s" in cfg.format


def test_logging_config_case_normalization():
    """Verifica normalização de maiúsculas/minúsculas e alias 'off'."""
    cfg1 = LoggingConfig(level="debug", destination="FILE")
    assert cfg1.level == "DEBUG"
    assert cfg1.destination == "file"

    cfg2 = LoggingConfig(destination="off")
    assert cfg2.destination == "none"


@pytest.mark.parametrize("invalid_level", ["VERBOSE", "TRACE", "INVALID", ""])
def test_logging_config_invalid_level(invalid_level):
    """Verifica que níveis inválidos geram erro de validação."""
    with pytest.raises(ValidationError):
        LoggingConfig(level=invalid_level)


@pytest.mark.parametrize("invalid_dest", ["socket", "syslog", "invalid"])
def test_logging_config_invalid_destination(invalid_dest):
    """Verifica que destinos inválidos geram erro de validação."""
    with pytest.raises(ValidationError):
        LoggingConfig(destination=invalid_dest)


def test_get_logger_namespacing():
    """Verifica namespace uniforme sob ctrl_prj."""
    root_ctrl = get_logger()
    assert root_ctrl.name == "ctrl_prj"

    scanner_log = get_logger("scanner")
    assert scanner_log.name == "ctrl_prj.scanner"

    already_prefixed = get_logger("ctrl_prj.scanner")
    assert already_prefixed.name == "ctrl_prj.scanner"


def test_setup_logging_console(capsys):
    """Verifica emissão em console."""
    cfg = LoggingConfig(level="INFO", destination="console")
    logger = setup_logging(cfg)

    handlers = logger.handlers
    assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, CompressedRotatingFileHandler) for h in handlers)
    assert not any(isinstance(h, CompressedRotatingFileHandler) for h in handlers)

    logger.info("Mensagem de teste console")
    captured = capsys.readouterr()
    assert "Mensagem de teste console" in captured.out

    reset_logging()


def test_setup_logging_file(tmp_path):
    """Verifica emissão exclusiva em arquivo de log."""
    log_file = tmp_path / "sub" / "app.log"
    cfg = LoggingConfig(level="DEBUG", destination="file", file_path=log_file)
    logger = setup_logging(cfg)

    handlers = logger.handlers
    assert any(isinstance(h, CompressedRotatingFileHandler) for h in handlers)
    assert not any(type(h) is logging.StreamHandler for h in handlers)

    logger.debug("Mensagem gravada no arquivo")
    reset_logging()

    assert log_file.is_file()
    content = log_file.read_text(encoding="utf-8")
    assert "Mensagem gravada no arquivo" in content
    assert "[DEBUG]" in content


def test_setup_logging_both(tmp_path, capsys):
    """Verifica emissão simultânea no console e no arquivo."""
    log_file = tmp_path / "both.log"
    cfg = LoggingConfig(level="WARNING", destination="both", file_path=log_file)
    logger = setup_logging(cfg)

    logger.warning("Alerta geral emitido!")
    reset_logging()

    # Verifica console
    captured = capsys.readouterr()
    assert "Alerta geral emitido!" in captured.out

    # Verifica arquivo
    assert log_file.is_file()
    content = log_file.read_text(encoding="utf-8")
    assert "Alerta geral emitido!" in content
    assert "[WARNING]" in content


def test_setup_logging_none(tmp_path, capsys):
    """Verifica que destination='none' silencia as saídas."""
    log_file = tmp_path / "silent.log"
    cfg = LoggingConfig(level="DEBUG", destination="none", file_path=log_file)
    logger = setup_logging(cfg)

    logger.error("Erro que não deve sair")
    reset_logging()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert not log_file.exists()


def test_setup_logging_cli_overrides(tmp_path):
    """Verifica que argumentos da CLI sobrescrevem a configuração do arquivo."""
    log_file = tmp_path / "cli_override.log"
    cfg = LoggingConfig(level="ERROR", destination="console", file_path=log_file)

    # CLI força DEBUG e destination=file
    logger = setup_logging(cfg, cli_level="DEBUG", cli_destination="file")
    assert logger.level == logging.DEBUG

    logger.debug("Debug ativado via CLI")
    reset_logging()

    assert log_file.is_file()
    assert "Debug ativado via CLI" in log_file.read_text(encoding="utf-8")


def test_log_rotation_and_gzip_compression(tmp_path):
    """Verifica a rotação de logs por tamanho com compressão gzip e retenção de N versões."""
    log_file = tmp_path / "rot.log"
    max_bytes = 100
    backup_count = 2

    handler = CompressedRotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        compress=True,
    )
    test_logger = logging.getLogger("ctrl_prj.test_rot")
    test_logger.setLevel(logging.INFO)
    test_logger.addHandler(handler)

    # Escreve mensagens para acionar múltiplos rollovers
    for i in range(15):
        test_logger.info(f"Linha de log número {i:02d} com texto longo preenchendo bytes.")

    handler.close()
    test_logger.removeHandler(handler)

    # Arquivo ativo deve existir
    assert log_file.exists()

    # Backups comprimidos devem existir
    gz_1 = tmp_path / "rot.log.1.gz"
    gz_2 = tmp_path / "rot.log.2.gz"
    gz_3 = tmp_path / "rot.log.3.gz"

    assert gz_1.exists(), "rot.log.1.gz deve existir"
    assert gz_2.exists(), "rot.log.2.gz deve existir"
    assert not gz_3.exists(), "rot.log.3.gz NÃO deve existir porque backupCount=2"

    # Descompacta e valida o conteúdo dos arquivos gz
    with gzip.open(gz_1, "rt", encoding="utf-8") as f:
        content_1 = f.read()
        assert "Linha de log número" in content_1

    with gzip.open(gz_2, "rt", encoding="utf-8") as f:
        content_2 = f.read()
        assert "Linha de log número" in content_2
