"""Configuração e inicialização do sistema de logging do ctrl_prj."""

import logging
from pathlib import Path
import sys
from typing import Optional

from ctrl_prj.config.settings import LoggingConfig
from ctrl_prj.log.handler import CompressedRotatingFileHandler

LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

_CONFIGURED = False


def reset_logging() -> None:
    """Remove todos os handlers configurados para o namespace ctrl_prj e root logger."""
    global _CONFIGURED
    root_logger = logging.getLogger()
    ctrl_logger = logging.getLogger("ctrl_prj")

    for logger in (root_logger, ctrl_logger):
        for handler in list(logger.handlers):
            try:
                handler.close()
            except Exception:
                pass
            logger.removeHandler(handler)

    _CONFIGURED = False


def setup_logging(
    config: Optional[LoggingConfig] = None,
    cli_level: Optional[str] = None,
    cli_destination: Optional[str] = None,
) -> logging.Logger:
    """Configura o sistema de logging do ctrl_prj.

    Args:
        config: Instância de LoggingConfig. Se None, usa valores padrão.
        cli_level: Override do nível de log vindo da CLI (DEBUG, INFO, WARNING, ERROR).
        cli_destination: Override do destino vindo da CLI (console, file, both, none).

    Returns:
        logging.Logger: Logger raiz do namespace 'ctrl_prj'.
    """
    global _CONFIGURED

    if config is None:
        config = LoggingConfig()

    # Nível efetivo de log
    raw_level = (cli_level or config.level).strip().upper()
    log_level = LEVEL_MAP.get(raw_level, logging.INFO)

    # Destino efetivo
    destination = (cli_destination or config.destination).strip().lower()
    if destination == "off":
        destination = "none"

    reset_logging()

    ctrl_logger = logging.getLogger("ctrl_prj")
    ctrl_logger.setLevel(log_level)
    ctrl_logger.propagate = False

    formatter = logging.Formatter(config.format)

    if destination in ("console", "both"):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        ctrl_logger.addHandler(console_handler)

    if destination in ("file", "both"):
        log_file = Path(config.file_path).resolve()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        max_bytes = int(config.max_size_mb * 1024 * 1024)
        file_handler = CompressedRotatingFileHandler(
            filename=str(log_file),
            maxBytes=max_bytes,
            backupCount=config.max_backups,
            encoding="utf-8",
            compress=config.compress,
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        ctrl_logger.addHandler(file_handler)

    if destination == "none":
        ctrl_logger.addHandler(logging.NullHandler())

    _CONFIGURED = True
    return ctrl_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Obtém um logger associado ao namespace ctrl_prj.

    Args:
        name: Nome do componente/módulo (ex: __name__ ou 'scanner').
              Se começar com 'ctrl_prj', usa diretamente. Caso contrário,
              anexa como 'ctrl_prj.<name>'.

    Returns:
        logging.Logger: Instância do logger configurado.
    """
    if not name or name == "ctrl_prj":
        return logging.getLogger("ctrl_prj")
    if name.startswith("ctrl_prj."):
        return logging.getLogger(name)
    return logging.getLogger(f"ctrl_prj.{name}")
