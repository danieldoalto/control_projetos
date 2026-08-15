"""CLI interface for ctrl_prj."""

import argparse
from pathlib import Path
import sys
from typing import List, Optional

from ctrl_prj.config import ConfigError, load_config


def cmd_scan(args: argparse.Namespace) -> int:
    """Descobre e atualiza o estado do filesystem."""
    print(f"Executing 'scan' with config: {args.config}...")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analisa entidades novas ou modificadas."""
    print(f"Executing 'analyze' with config: {args.config}...")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Gera os relatórios Markdown."""
    print(f"Executing 'report' with config: {args.config}...")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Executa o pipeline completo: scan -> analyze -> report."""
    print("Running complete pipeline: scan -> analyze -> report")
    res_scan = cmd_scan(args)
    if res_scan != 0:
        return res_scan
    res_analyze = cmd_analyze(args)
    if res_analyze != 0:
        return res_analyze
    return cmd_report(args)


def build_parser() -> argparse.ArgumentParser:
    """Cria e configura o analisador de argumentos da CLI."""
    parser = argparse.ArgumentParser(
        prog="ctrl_prj",
        description="ctrl_prj: catalogação e identificação de projetos no filesystem.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Caminho do arquivo de configuração (padrão: config.yml)",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Comandos disponíveis",
    )

    # scan
    subparsers.add_parser(
        "scan",
        help="Descobre e atualiza o estado do filesystem (sem LLM)",
    )

    # analyze
    subparsers.add_parser(
        "analyze",
        help="Analisa entidades novas ou modificadas com LLM",
    )

    # report
    subparsers.add_parser(
        "report",
        help="Gera relatórios em Markdown",
    )

    # run
    subparsers.add_parser(
        "run",
        help="Executa o pipeline completo: scan -> analyze -> report",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Ponto de entrada principal da CLI."""
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    try:
        config = load_config(args.config)
        args.app_config = config
    except ConfigError as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 1

    command_map = {
        "scan": cmd_scan,
        "analyze": cmd_analyze,
        "report": cmd_report,
        "run": cmd_run,
    }

    handler = command_map.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
