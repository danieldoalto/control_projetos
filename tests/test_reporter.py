"""Testes para o módulo reporter (geração de relatórios Markdown)."""

import json
from pathlib import Path
import pytest

from ctrl_prj.cli import main
from ctrl_prj.config.settings import AppConfig
from ctrl_prj.memory import (
    AnalysisRecord,
    AnalysisRepository,
    Database,
    EntityRecord,
    EntityRepository,
    FileRecord,
    FileRepository,
    RootRecord,
    RootRepository,
)
from ctrl_prj.reporter import (
    generate_entity_report,
    generate_index,
    generate_reports,
    sanitize_filename,
)


def test_sanitize_filename():
    """Testa a sanitização de nomes de projetos para nomes de arquivo seguros."""
    assert sanitize_filename("Meu Projeto") == "meu-projeto"
    assert sanitize_filename("Projeto / Especial #1") == "projeto-especial-1"
    assert sanitize_filename("___my__app___") == "my-app"
    assert sanitize_filename("API-Service_v2.0") == "api-service-v20"
    assert sanitize_filename("   ") == "unnamed"


def test_generate_entity_report_with_analysis():
    """Testa geração do Markdown individual quando há análise do LLM."""
    entity = EntityRecord(
        id=1,
        root_id=1,
        path="/home/user/projects/web-api",
        name="web-api",
        type="project",
        status="analyzed",
        fingerprint="fp_12345",
    )
    analysis = AnalysisRecord(
        id=10,
        entity_id=1,
        name="Super Web API",
        type="application",
        description="API RESTful de alto desempenho.",
        purpose="Servir endpoints para o aplicativo mobile.",
        languages_json=json.dumps(["Python", "SQL"]),
        technologies_json=json.dumps(["FastAPI", "SQLAlchemy", "PostgreSQL"]),
        confidence=0.95,
        created_at="2026-08-15 12:00:00",
    )
    files = [
        FileRecord(
            id=101,
            entity_id=1,
            relative_path="main.py",
            file_hash="h1",
            size_bytes=2048,
            lines_count=60,
            language="python",
            is_code=True,
        ),
        FileRecord(
            id=102,
            entity_id=1,
            relative_path="README.md",
            file_hash="h2",
            size_bytes=512,
            lines_count=15,
            is_context=True,
        ),
    ]

    report = generate_entity_report(entity, analysis, files)

    # Valida Frontmatter YAML e Tags
    assert "---" in report
    assert "tags:" in report
    assert "- control_project" in report
    assert "Titulo: Super Web API" in report
    assert "Data: 2026-08-15" in report
    assert "Resumo: API RESTful de alto desempenho." in report

    # Valida bloco TOC do Obsidian
    assert "```table-of-contents" in report
    assert "style: nestedList" in report

    assert "# Super Web API" in report
    assert "> API RESTful de alto desempenho." in report
    assert "- **Tipo Semântico:** `application`" in report
    assert "- **Confiança da Análise:** `95%`" in report
    assert "Servir endpoints para o aplicativo mobile." in report
    assert "- Python" in report
    assert "- FastAPI" in report
    assert "`main.py`" in report
    assert "`README.md`" in report
    assert "2.0 KB" in report or "2048 B" in report



def test_generate_entity_report_without_analysis():
    """Testa geração do Markdown individual quando a entidade não possui análise LLM."""
    entity = EntityRecord(
        id=2,
        root_id=1,
        path="/home/user/scripts/backup.sh",
        name="backup.sh",
        type="script",
        status="new",
    )
    files = [
        FileRecord(
            id=201,
            entity_id=2,
            relative_path="backup.sh",
            file_hash="h_sh",
            size_bytes=300,
            lines_count=10,
            language="bash",
            is_code=True,
        )
    ]

    report = generate_entity_report(entity, None, files)

    assert "# backup.sh" in report
    assert "Nenhuma descrição gerada ainda" in report
    assert "- **Status:** `new`" in report
    assert "`backup.sh`" in report


def test_generate_index():
    """Testa a geração do arquivo INDEX.md agrupando por tipos semânticos."""
    e1 = EntityRecord(id=1, name="api-app", type="project")
    a1 = AnalysisRecord(
        id=1,
        entity_id=1,
        name="API App",
        type="application",
        description="Backend API",
        languages_json='["Python"]',
        technologies_json='["FastAPI"]',
    )

    e2 = EntityRecord(id=2, name="cli-tool", type="script")
    a2 = AnalysisRecord(
        id=2,
        entity_id=2,
        name="CLI Tool",
        type="cli",
        description="Ferramenta de linha de comando",
        languages_json='["Rust"]',
        technologies_json='["Clap"]',
    )

    e3 = EntityRecord(id=3, name="pending-proj", type="project")

    entries = [
        (e1, a1, "projects/api-app.md"),
        (e2, a2, "projects/cli-tool.md"),
        (e3, None, "projects/pending-proj.md"),
    ]

    index_md = generate_index(entries, Path("/tmp/reports"))

    assert "# 📚 Catálogo de Projetos — ctrl_prj" in index_md
    assert "- **Total de Entidades:** 3" in index_md
    assert "- **Analisadas:** 2" in index_md
    assert "- **Pendentes / Sem Análise:** 1" in index_md
    assert "Applications & Services" in index_md
    assert "CLI & Utilities" in index_md
    assert "Outros / Não Classificados" in index_md
    assert "[API App](projects/api-app.md)" in index_md
    assert "[CLI Tool](projects/cli-tool.md)" in index_md
    assert "[pending-proj](projects/pending-proj.md)" in index_md


def test_generate_reports_full_flow(tmp_path: Path):
    """Testa o fluxo completo de geração de relatórios com escrita no filesystem."""
    db_path = tmp_path / "data.db"
    reports_dir = tmp_path / "reports_out"
    db = Database(db_path)

    config = AppConfig(
        database={"path": str(db_path)},
        reporter={"output_dir": str(reports_dir), "device": "test-box"},
    )

    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        analysis_repo = AnalysisRepository(conn)
        file_repo = FileRepository(conn)

        root = root_repo.get_or_create(str(tmp_path))

        # Entidade 1
        e1 = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,  # type: ignore
                path=str(tmp_path / "proj1"),
                name="Projeto Alpha",
                type="project",
                status="analyzed",
            )
        )
        analysis_repo.create(
            AnalysisRecord(
                entity_id=e1.id,  # type: ignore
                name="Alpha Engine",
                type="library",
                description="Biblioteca central de cálculo.",
                purpose="Processar matrizes matemáticas.",
                languages_json='["Python"]',
                technologies_json='["NumPy"]',
            )
        )
        file_repo.upsert(
            FileRecord(
                entity_id=e1.id,  # type: ignore
                relative_path="alpha.py",
                file_hash="h_alpha",
                size_bytes=1024,
                lines_count=30,
                is_code=True,
            )
        )

        # Entidade 2 (sem análise, mesmo nome para testar desambiguação)
        e2 = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,  # type: ignore
                path=str(tmp_path / "proj2"),
                name="Projeto Alpha",
                type="project",
                status="new",
            )
        )

    # Executa a geração de relatórios
    res = generate_reports(config, db, output_dir=reports_dir)

    assert res.total_entities == 2
    assert res.total_reports == 2
    assert reports_dir.exists()
    assert (reports_dir / "test-box-INDEX.md").exists()
    assert (reports_dir / "projects").is_dir()

    # Verifica os arquivos individuais gerados (incluindo o desambiguado com prefixo do dispositivo)
    files = list((reports_dir / "projects").glob("test-box-*.md"))
    assert len(files) == 2

    # Verifica conteúdo do INDEX
    index_content = (reports_dir / "test-box-INDEX.md").read_text(encoding="utf-8")
    assert "Alpha Engine" in index_content
    assert "Projeto Alpha" in index_content
    assert "test-box" in index_content


def test_cli_report_integration(tmp_path: Path, capsys):
    """Testa a execução do comando 'report' via CLI com flag -o."""
    db_path = tmp_path / "data.db"
    out_dir = tmp_path / "custom_reports"
    db = Database(db_path)

    config_file = tmp_path / "config.yml"
    config_file.write_text(
        f"""
device: my-machine
database:
  path: "{db_path.as_posix()}"
reporter:
  output_dir: "{out_dir.as_posix()}"
""",
        encoding="utf-8",
    )

    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        root = root_repo.get_or_create(str(tmp_path))
        entity_repo.upsert(
            EntityRecord(
                root_id=root.id,  # type: ignore
                path=str(tmp_path / "cli_sample"),
                name="CLI Sample",
                type="script",
            )
        )

    exit_code = main(["-c", str(config_file), "report", "-o", str(out_dir)])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Gerando relatórios Markdown" in captured.out
    assert "Total de entidades processadas: 1" in captured.out
    assert "Índice consolidado" in captured.out
    assert (out_dir / "my-machine-INDEX.md").exists()
    assert (out_dir / "projects" / "my-machine-cli-sample.md").exists()


def test_generate_index_with_roots_and_individuals(tmp_path: Path):
    """Testa a geração do INDEX.md dividindo raízes contêineres e projetos individuais."""
    e1 = EntityRecord(id=1, root_id=10, path="/home/daniel/projetos/proj1", name="proj1", type="project")
    a1 = AnalysisRecord(id=1, entity_id=1, name="Project One", type="application", description="App in root")

    e2 = EntityRecord(id=2, root_id=20, path="/home/daniel/avulso/script.py", name="script", type="script")
    a2 = AnalysisRecord(id=2, entity_id=2, name="Avulso Script", type="script", description="Individual script")

    entries = [
        (e1, a1, "projects/proj1.md"),
        (e2, a2, "projects/script.md"),
    ]

    roots_map = {
        10: "/home/daniel/projetos",
        20: "/home/daniel/avulso/script.py",
    }
    config_roots = [Path("/home/daniel/projetos")]
    config_individuals = [Path("/home/daniel/avulso/script.py")]

    index_md = generate_index(
        entries=entries,
        output_dir=tmp_path,
        roots_map=roots_map,
        config_roots=config_roots,
        config_individuals=config_individuals,
    )

    assert "## 📊 Sumário Geral" in index_md
    assert "### 📁 Raízes de Projetos (`roots`)" in index_md
    assert "`/home/daniel/projetos`" in index_md
    assert "### 📦 Projetos Individuais (`individual_projects`)" in index_md
    assert "`/home/daniel/avulso/script.py`" in index_md
    assert "## 📁 Raiz: `/home/daniel/projetos`" in index_md
    assert "## 📦 Projetos Individuais" in index_md
    assert "[Project One](projects/proj1.md)" in index_md
    assert "[Avulso Script](projects/script.md)" in index_md


def test_generate_reports_with_target_paths_preserves_index(tmp_path: Path):
    """Garante que a geração de relatórios direcionada a uma pasta específica não sobrescreva o INDEX.md global."""
    from ctrl_prj.config import AppConfig, ReporterConfig
    from ctrl_prj.memory import Database, EntityRepository

    db_file = tmp_path / "test_rep_target.db"
    db = Database(db_file)

    with db.get_connection() as conn:
        from ctrl_prj.memory import RootRepository
        root_rec = RootRepository(conn).get_or_create(str(tmp_path))
        repo = EntityRepository(conn)
        repo.upsert(EntityRecord(root_id=root_rec.id, path=str(tmp_path / "app1"), name="app1", type="project"))
        repo.upsert(EntityRecord(root_id=root_rec.id, path=str(tmp_path / "app2"), name="app2", type="project"))

    out_dir = tmp_path / "reports"
    out_dir.mkdir()
    index_file = out_dir / "test-device-INDEX.md"
    original_index_content = "# Meu INDEX Geral Completo Antigo"
    index_file.write_text(original_index_content, encoding="utf-8")

    config = AppConfig(
        device="test-device",
        reporter=ReporterConfig(output_dir=out_dir),
    )

    # Executa report direcionado apenas para app1
    target = tmp_path / "app1"
    result = generate_reports(config, db, output_dir=out_dir, target_paths=[target])

    assert result.total_reports == 1
    assert result.index_path is None
    # Verifica que o relatório do app1 foi gerado
    assert (out_dir / "projects" / "test-device-app1.md").exists()
    # Verifica que o INDEX.md original permaneceu intacto
    assert index_file.read_text(encoding="utf-8") == original_index_content


