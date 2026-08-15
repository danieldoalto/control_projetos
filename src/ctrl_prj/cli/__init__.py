"""CLI interface for ctrl_prj."""

import argparse
from pathlib import Path
import sys
from typing import List, Optional

from ctrl_prj.config import ConfigError, load_config
from ctrl_prj.memory import Database
from ctrl_prj.scanner import ScanResult, run_scan


def cmd_scan(args: argparse.Namespace) -> int:
    """Descobre e atualiza o estado do filesystem."""
    config = getattr(args, "app_config", None)
    if not config:
        config = load_config(args.config)

    if not config.roots:
        print("Nenhuma raiz ('roots') configurada para escanear.")
        print("Adicione raízes no seu arquivo config.yml.")
        return 0

    db = Database(config.database.path)
    print("🔍 Iniciando varredura do filesystem...")
    result: ScanResult = run_scan(config, db)

    print(f"📁 Raízes processadas: {result.roots_scanned}")
    print(f"📦 Total de entidades encontradas: {result.total_entities}")
    print(f"   ✨ Novas: {result.new_count}")
    print(f"   🔄 Modificadas: {result.changed_count}")
    print(f"   ✔️  Inalteradas: {result.unchanged_count}")
    if result.missing_count > 0:
        print(f"   ⚠️  Ausentes no filesystem: {result.missing_count}")
    print(f"📄 Total de arquivos catalogados: {result.total_files}")

    # Exibe resumo de entidades se houver novidades
    if result.entity_summaries:
        for ent in result.entity_summaries:
            if ent.status == "new":
                print(f"  [+] Nova entidade: {ent.name} ({ent.type}) -> {ent.files_count} arquivos")
            elif ent.status == "changed":
                print(f"  [*] Entidade modificada: {ent.name} ({ent.type})")
            elif ent.status == "missing":
                print(f"  [-] Entidade não encontrada (missing): {ent.name}")

    print("✅ Varredura concluída com sucesso.")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analisa entidades novas ou modificadas."""
    print("Executing 'analyze'...")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Gera os relatórios Markdown."""
    print("Executing 'report'...")
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
