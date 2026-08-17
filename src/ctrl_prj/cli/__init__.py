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




def _extract_target_paths(args: argparse.Namespace) -> Optional[List[Path]]:
    """Extrai e normaliza caminhos de projetos/pastas passados via CLI."""
    raw_paths: List[str] = []
    if getattr(args, "paths", None):
        raw_paths.extend(args.paths)
    if getattr(args, "opt_paths", None):
        raw_paths.extend(args.opt_paths)
    if not raw_paths:
        return None
    return [Path(p).expanduser().resolve() for p in raw_paths]


def cmd_scan(args: argparse.Namespace) -> int:
    """Descobre e atualiza o estado do filesystem."""
    config = getattr(args, "app_config", None)
    if not config:
        config = load_config(args.config)

    target_paths = _extract_target_paths(args)

    if not target_paths and not config.roots and not config.individual_projects:
        print("Nenhuma raiz ('roots') ou projeto individual ('individual_projects') configurado para escanear.")
        print("Adicione raízes ou projetos no seu arquivo config.yml ou passe caminhos via CLI: ctrl_prj scan <caminho>")
        logger.warning("Comando scan abortado: nenhuma raiz ou projeto configurado.")
        return 0

    db = Database(config.database.path)
    if target_paths:
        print(f"🔍 Iniciando varredura direcionada para {len(target_paths)} caminho(s) especificado(s)...")
        for tp in target_paths:
            print(f"   🎯 Alvo: {tp}")
    else:
        print("🔍 Iniciando varredura do filesystem...")

    force = getattr(args, "force", False)
    logger.info(f"Executando comando scan (force={force}, target_paths={target_paths})...")
    result: ScanResult = run_scan(config, db, force=force, target_paths=target_paths)

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
    target_paths = _extract_target_paths(args)

    logger.info(f"Executando comando analyze (force={force}, target_paths={target_paths})...")
    if force:
        print("🔍 Buscando TODAS as entidades para análise forçada (--force)...")
    else:
        print("🔍 Buscando entidades pendentes para análise...")

    if target_paths:
        print(f"   🎯 Limitando análise a {len(target_paths)} caminho(s) especificado(s).")

    def on_progress(idx: int, total: int, entity, analysis_result, error_msg):
        if error_msg:
            print(f"  [{idx}/{total}] ⚠️  Erro ao analisar '{entity.name}': {error_msg}")
        elif analysis_result:
            langs = f" ({', '.join(analysis_result.languages)})" if analysis_result.languages else ""
            print(f"  [{idx}/{total}] ✨ Analisado: {entity.name} -> Tipo: {analysis_result.type}{langs}")

    result = run_analyze(config, db, on_progress=on_progress, force=force, target_paths=target_paths)

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
    target_paths = _extract_target_paths(args)

    logger.info(f"Executando comando report (output_dir={output_dir}, target_paths={target_paths})...")
    print(f"📊 Gerando relatórios Markdown em '{output_dir}'...")
    if target_paths:
        print(f"   🎯 Limitando relatórios a {len(target_paths)} caminho(s) especificado(s).")

    result = generate_reports(config, db, output_dir=output_dir, target_paths=target_paths)

    print(f"📁 Diretório de saída: {result.output_dir}")
    print(f"📦 Total de entidades processadas: {result.total_entities}")
    print(f"📄 Relatórios individuais criados: {result.total_reports} em 'projects/'")
    if result.index_path:
        print(f"📚 Índice consolidado: '{result.index_path}'")
    else:
        print("📚 Índice consolidado: preservado intacto (execução direcionada)")
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
    """Cria e configura o analisador de argumentos da CLI com documentação e exemplos."""
    parser = argparse.ArgumentParser(
        prog="ctrl_prj",
        description="""
ctrl_prj: catalogação, análise incremental com IA e geração de relatórios para Obsidian.

Comandos disponíveis:
  scan      Varre o filesystem, detecta projetos e calcula fingerprints (sem IA)
  analyze   Executa interpretação semântica com IA nas entidades novas/modificadas
  report    Gera relatórios individuais em Markdown e o índice geral INDEX.md
  run       Executa o pipeline completo integrado: scan -> analyze -> report
""",
        epilog="""
Exemplos de uso geral:
  # Executar pipeline completo em todo o repositório:
  ctrl_prj run

  # Escanear ou analisar apenas uma pasta ou projeto específico:
  ctrl_prj scan D:\\Projetos\\openwebui
  ctrl_prj analyze D:\\Projetos\\openwebui
  ctrl_prj report D:\\Projetos\\openwebui

  # Executar pipeline completo em múltiplos projetos específicos:
  ctrl_prj run /home/user/app1 /home/user/app2

  # Gerar relatórios ocultando entidades 'missing' (não encontradas):
  ctrl_prj report --exclude-missing

  # Inspecionar tráfego de rede e prompts do LLM em tempo real:
  ctrl_prj --llm-traffic full analyze
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Caminho do arquivo de configuração alternativo (padrão: config.yml)",
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
        help="Nível de auditoria do tráfego LLM (none, basic, full)",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Comandos disponíveis",
    )

    # scan
    scan_parser = subparsers.add_parser(
        "scan",
        help="Descobre e atualiza o estado do filesystem no SQLite (sem IA)",
        description="""
Descobre entidades, varre arquivos relevantes, calcula hashes SHA-256 e armazena o estado no banco SQLite.
Não realiza chamadas de IA.
""",
        epilog="""
Exemplos:
  # Escanear todas as raízes e projetos configurados no config.yml:
  ctrl_prj scan

  # Escanear apenas uma pasta ou projeto específico:
  ctrl_prj scan D:\\Projetos\\openwebui
  ctrl_prj scan ~/projetos/meu-app

  # Escanear múltiplos projetos de uma vez:
  ctrl_prj scan /caminho/proj1 /caminho/proj2

  # Forçar sincronização e purga de arquivos excluídos:
  ctrl_prj scan --force
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scan_parser.add_argument(
        "paths",
        nargs="*",
        default=None,
        help="Uma ou mais pastas ou projetos específicos para escanear",
    )
    scan_parser.add_argument(
        "-p",
        "--paths",
        dest="opt_paths",
        nargs="+",
        default=None,
        help="Pastas específicas para escanear (alias para caminhos posicionais)",
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
        description="""
Consulta entidades com status 'new', 'changed' ou 'error' no SQLite, constrói o contexto
estrutural leve (AST, classes, imports) e envia ao LLM para enriquecimento semântico.
""",
        epilog="""
Exemplos:
  # Analisar todas as entidades pendentes de análise:
  ctrl_prj analyze

  # Analisar apenas um projeto ou pasta específica:
  ctrl_prj analyze D:\\Projetos\\openwebui

  # Forçar reanálise com IA de todas as entidades (mesmo já analisadas):
  ctrl_prj analyze --force

  # Forçar reanálise apenas de um projeto específico:
  ctrl_prj analyze -f D:\\Projetos\\openwebui
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analyze_parser.add_argument(
        "paths",
        nargs="*",
        default=None,
        help="Uma ou mais pastas ou projetos específicos para analisar",
    )
    analyze_parser.add_argument(
        "-p",
        "--paths",
        dest="opt_paths",
        nargs="+",
        default=None,
        help="Pastas específicas para analisar",
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
        help="Gera relatórios em Markdown e o catálogo consolidado INDEX.md",
        description="""
Gera relatórios individuais em formato Markdown na pasta 'projects/' e cria o catálogo mestre INDEX.md.
Se executado para projetos específicos, atualiza apenas seus relatórios individuais e preserva o INDEX.md geral.
""",
        epilog="""
Exemplos:
  # Gerar relatórios para todas as entidades e atualizar o INDEX.md:
  ctrl_prj report

  # Gerar relatórios apenas para um projeto específico (preserva o INDEX.md intacto):
  ctrl_prj report D:\\Projetos\\openwebui

  # Ocultar projetos com status 'missing' (não encontrados no disco):
  ctrl_prj report --exclude-missing

  # Especificar pasta de saída customizada:
  ctrl_prj report -o ./meus_relatorios
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    report_parser.add_argument(
        "paths",
        nargs="*",
        default=None,
        help="Uma ou mais pastas ou projetos específicos para gerar relatórios",
    )
    report_parser.add_argument(
        "-p",
        "--paths",
        dest="opt_paths",
        nargs="+",
        default=None,
        help="Pastas específicas para gerar relatórios",
    )
    report_parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Diretório de saída para os relatórios Markdown (padrão: reports/)",
    )
    report_parser.add_argument(
        "--exclude-missing",
        action="store_true",
        default=None,
        help="Oculta entidades com status 'missing' (não encontradas) dos relatórios e do INDEX.md",
    )
    report_parser.add_argument(
        "--include-missing",
        action="store_true",
        default=None,
        help="Inclui entidades com status 'missing' nos relatórios e no INDEX.md",
    )

    # run
    run_parser = subparsers.add_parser(
        "run",
        help="Executa o pipeline completo: scan -> analyze -> report",
        description="""
Executa o fluxo completo integrado em sequência:
  1. SCAN: Varredura e descoberta no filesystem
  2. ANALYZE: Interpretação semântica com IA
  3. REPORT: Geração de relatórios Markdown e índice Obsidian
""",
        epilog="""
Exemplos:
  # Executar o pipeline completo em todo o repositório:
  ctrl_prj run

  # Executar o pipeline completo apenas em um projeto específico:
  ctrl_prj run D:\\Projetos\\openwebui

  # Executar ocultando entidades 'missing' dos relatórios:
  ctrl_prj run --exclude-missing

  # Forçar re-escaneamento e reanálise total de tudo:
  ctrl_prj run --force
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument(
        "paths",
        nargs="*",
        default=None,
        help="Uma ou mais pastas ou projetos específicos para executar o pipeline",
    )
    run_parser.add_argument(
        "-p",
        "--paths",
        dest="opt_paths",
        nargs="+",
        default=None,
        help="Pastas específicas para executar o pipeline",
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
    run_parser.add_argument(
        "--exclude-missing",
        action="store_true",
        default=None,
        help="Oculta entidades com status 'missing' dos relatórios e do INDEX.md",
    )
    run_parser.add_argument(
        "--include-missing",
        action="store_true",
        default=None,
        help="Inclui entidades com status 'missing' nos relatórios e no INDEX.md",
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
        if getattr(args, "exclude_missing", None):
            config.reporter.include_missing = False
        elif getattr(args, "include_missing", None):
            config.reporter.include_missing = True
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
