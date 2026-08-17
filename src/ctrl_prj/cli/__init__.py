"""CLI interface for ctrl_prj."""

import argparse
from pathlib import Path
import sys
from typing import List, Optional

from ctrl_prj.analyzer import run_analyze
from ctrl_prj.config import ConfigError, load_config
from ctrl_prj.log import get_logger, setup_logging
from ctrl_prj.memory import Database
from ctrl_prj.reporter import generate_reports
from ctrl_prj.scanner import ScanResult, run_scan

logger = get_logger(__name__)




def cmd_scan(args: argparse.Namespace) -> int:
    """Descobre e atualiza o estado do filesystem."""
    config = getattr(args, "app_config", None)
    if not config:
        config = load_config(args.config)

    if not config.roots and not config.individual_projects:
        print("Nenhuma raiz ('roots') ou projeto individual ('individual_projects') configurado para escanear.")
        print("Adicione raízes ou projetos no seu arquivo config.yml.")
        logger.warning("Comando scan abortado: nenhuma raiz ou projeto configurado.")
        return 0

    db = Database(config.database.path)
    print("🔍 Iniciando varredura do filesystem...")
    force = getattr(args, "force", False)
    logger.info(f"Executando comando scan (force={force})...")
    result: ScanResult = run_scan(config, db, force=force)

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
    logger.info("Comando scan finalizado com sucesso.")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analisa entidades novas ou modificadas com LLM."""
    config = getattr(args, "app_config", None)
    if not config:
        config = load_config(args.config)

    db = Database(config.database.path)
    force = getattr(args, "force", False)
    logger.info(f"Executando comando analyze (force={force})...")
    if force:
        print("🔍 Buscando TODAS as entidades para análise forçada (--force)...")
    else:
        print("🔍 Buscando entidades pendentes para análise...")

    def on_progress(idx: int, total: int, entity, analysis_result, error_msg):
        if error_msg:
            print(f"  [{idx}/{total}] ⚠️  Erro ao analisar '{entity.name}': {error_msg}")
        elif analysis_result:
            langs = f" ({', '.join(analysis_result.languages)})" if analysis_result.languages else ""
            print(f"  [{idx}/{total}] ✨ Analisado: {entity.name} -> Tipo: {analysis_result.type}{langs}")

    result = run_analyze(config, db, on_progress=on_progress, force=force)

    if result.total_pending == 0:
        print("ℹ️  Nenhuma entidade pendente de análise (todas já analisadas ou inalteradas).")
        if result.already_analyzed_count > 0:
            print(f"   ({result.already_analyzed_count} entidades já estavam atualizadas no banco de dados).")
        logger.info("Comando analyze finalizado: nenhuma entidade pendente.")
        return 0

    print("\n📊 Resumo da Análise:")
    print(f"   ✨ Analisadas com sucesso: {result.analyzed_count}")
    if result.error_count > 0:
        print(f"   ⚠️  Falhas / Erros: {result.error_count}")
    if result.already_analyzed_count > 0:
        print(f"   ✔️  Já atualizadas anteriormente: {result.already_analyzed_count}")

    logger.info(
        f"Comando analyze finalizado: {result.analyzed_count} analisadas, "
        f"{result.error_count} erros, {result.already_analyzed_count} inalteradas."
    )
    if result.error_count > 0 and result.analyzed_count == 0:
        return 1
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Gera os relatórios Markdown a partir do estado SQLite."""
    config = getattr(args, "app_config", None)
    if not config:
        config = load_config(args.config)

    db = Database(config.database.path)
    output_dir = Path(getattr(args, "output", None) or config.reporter.output_dir).expanduser().resolve()

    logger.info(f"Executando comando report (output_dir={output_dir})...")
    print(f"📊 Gerando relatórios Markdown em '{output_dir}'...")
    result = generate_reports(config, db, output_dir=output_dir)

    print(f"📁 Diretório de saída: {result.output_dir}")
    print(f"📦 Total de entidades processadas: {result.total_entities}")
    print(f"📄 Relatórios individuais criados: {result.total_reports} em 'projects/'")
    print(f"📚 Índice consolidado: '{result.index_path}'")
    print("✅ Geração de relatórios concluída com sucesso.")
    logger.info(f"Comando report finalizado: {result.total_reports} relatórios gerados.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Executa o pipeline completo: scan -> analyze -> report."""
    logger.info("Iniciando pipeline unificado: RUN (scan -> analyze -> report)...")
    print("=" * 60)
    print("🔍 FASE 1/3: SCAN (Varredura e Descoberta no Filesystem)")
    print("=" * 60)
    res_scan = cmd_scan(args)
    if res_scan != 0:
        logger.error("Pipeline interrompido devido a erro na fase de SCAN.")
        print("\n❌ Pipeline interrompido devido a erro crítico na fase de SCAN.")
        return res_scan

    print("\n" + "=" * 60)
    print("🧠 FASE 2/3: ANALYZE (Interpretação Semântica com LLM)")
    print("=" * 60)
    cmd_analyze(args)

    print("\n" + "=" * 60)
    print("📊 FASE 3/3: REPORT (Geração de Relatórios Markdown)")
    print("=" * 60)
    res_report = cmd_report(args)

    print("\n" + "=" * 60)
    print("🎉 Pipeline unificado (scan -> analyze -> report) finalizado!")
    print("=" * 60)
    logger.info("Pipeline unificado RUN finalizado com sucesso.")
    return res_report


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
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "debug", "info", "warning", "error"],
        help="Nível de log para a execução (DEBUG, INFO, WARNING, ERROR)",
    )
    parser.add_argument(
        "--log-dest",
        default=None,
        choices=["console", "file", "both", "none", "CONSOLE", "FILE", "BOTH", "NONE", "off", "OFF"],
        help="Destino dos logs (console, file, both, none)",
    )
    parser.add_argument(
        "--llm-traffic",
        default=None,
        choices=["none", "basic", "full", "nenhum", "basico", "básico", "completo"],
        help="Nível de log do tráfego LLM (none, basic, full)",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Comandos disponíveis",
    )

    # scan
    scan_parser = subparsers.add_parser(
        "scan",
        help="Descobre e atualiza o estado do filesystem (sem LLM)",
    )
    scan_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Força a sincronização e purga de arquivos excluídos em todas as entidades",
    )

    # analyze
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analisa entidades novas ou modificadas com LLM",
    )
    analyze_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Força reanálise com LLM de todas as entidades, mesmo já analisadas",
    )

    # report
    report_parser = subparsers.add_parser(
        "report",
        help="Gera relatórios em Markdown",
    )
    report_parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Diretório de saída para os relatórios Markdown (padrão: reports/)",
    )

    # run
    run_parser = subparsers.add_parser(
        "run",
        help="Executa o pipeline completo: scan -> analyze -> report",
    )
    run_parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Diretório de saída para os relatórios Markdown (padrão: reports/)",
    )
    run_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Força re-escaneamento e reanálise de todas as entidades",
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
        if args.llm_traffic:
            config.llm.traffic_log = args.llm_traffic
        args.app_config = config
        setup_logging(
            config=config.logging,
            cli_level=args.log_level,
            cli_destination=args.log_dest,
        )
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
