"""Testes de integração End-to-End (E2E) para o comando 'run' e o pipeline unificado."""

from pathlib import Path
import pytest

from ctrl_prj.cli import main
from ctrl_prj.memory import (
    AnalysisRepository,
    Database,
    EntityRepository,
    FileRepository,
    RootRepository,
)


@pytest.fixture
def e2e_workspace(tmp_path: Path):
    """Cria um ambiente de teste isolado com múltiplos projetos e configuração."""
    workspace_dir = tmp_path / "my_workspace"
    workspace_dir.mkdir()

    # Projeto 1: Aplicação Python
    proj_a = workspace_dir / "backend_service"
    proj_a.mkdir()
    (proj_a / "pyproject.toml").write_text(
        '[project]\nname = "backend_service"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (proj_a / "server.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'status': 'ok'}\n",
        encoding="utf-8",
    )
    (proj_a / "README.md").write_text(
        "# Backend Service\nServiço backend de autenticação e dados.\n",
        encoding="utf-8",
    )

    # Projeto 2: Script de Automação
    proj_b = workspace_dir / "scripts_deploy"
    proj_b.mkdir()
    (proj_b / ".ctrl_prj").write_text("type=script\n", encoding="utf-8")
    (proj_b / "deploy.sh").write_text(
        "#!/usr/bin/env bash\necho 'Deploying containers...'\n",
        encoding="utf-8",
    )

    # Configuração
    db_path = tmp_path / "database.db"
    reports_dir = tmp_path / "final_reports"
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        f"""
device: e2e-node
database:
  path: "{db_path.as_posix()}"
llm:
  provider: "mock"
reporter:
  output_dir: "{reports_dir.as_posix()}"
roots:
  - "{workspace_dir.as_posix()}"
""",
        encoding="utf-8",
    )

    return {
        "tmp_path": tmp_path,
        "workspace_dir": workspace_dir,
        "proj_a": proj_a,
        "proj_b": proj_b,
        "db_path": db_path,
        "reports_dir": reports_dir,
        "config_file": config_file,
    }


def test_full_e2e_pipeline_execution(e2e_workspace, capsys):
    """Testa a execução completa do pipeline: scan -> analyze -> report via 'ctrl_prj run'."""
    config_file: Path = e2e_workspace["config_file"]
    db_path: Path = e2e_workspace["db_path"]
    reports_dir: Path = e2e_workspace["reports_dir"]

    # 1. Executa o pipeline inicial
    exit_code = main(["-c", str(config_file), "run"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "FASE 1/3: SCAN" in captured.out
    assert "FASE 2/3: ANALYZE" in captured.out
    assert "FASE 3/3: REPORT" in captured.out
    assert "Pipeline unificado (scan -> analyze -> report) finalizado!" in captured.out

    # 2. Valida persistência no SQLite
    db = Database(db_path)
    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        analysis_repo = AnalysisRepository(conn)
        file_repo = FileRepository(conn)

        roots = root_repo.list_all()
        assert len(roots) == 1

        entities = entity_repo.list_all()
        assert len(entities) == 2

        for ent in entities:
            assert ent.status == "analyzed"
            assert ent.fingerprint is not None

            # Verifica se arquivos foram indexados
            files = file_repo.list_by_entity(ent.id)  # type: ignore
            assert len(files) >= 1

            # Verifica se a análise foi gravada
            analysis = analysis_repo.get_latest_by_entity(ent.id)  # type: ignore
            assert analysis is not None
            assert analysis.name != ""
            assert analysis.type != ""

    # 3. Valida geração dos arquivos Markdown de relatório
    assert reports_dir.exists()
    index_md = reports_dir / "e2e-node-INDEX.md"
    assert index_md.exists()
    index_content = index_md.read_text(encoding="utf-8")
    assert "Catálogo de Projetos (e2e-node) — ctrl_prj" in index_content
    assert "**Total de Entidades:** 2" in index_content
    assert "**Analisadas:** 2" in index_content



    projects_dir = reports_dir / "projects"
    assert projects_dir.is_dir()
    proj_reports = list(projects_dir.glob("*.md"))
    assert len(proj_reports) == 2

    for r_file in proj_reports:
        content = r_file.read_text(encoding="utf-8")
        assert "## 📋 Visão Geral" in content
        assert "## 🎯 Propósito" in content
        assert "## 📁 Arquivos Relevantes" in content

    # 4. Executa uma segunda vez e valida idempotência / incrementalidade
    exit_code_2 = main(["-c", str(config_file), "run"])
    assert exit_code_2 == 0

    captured_2 = capsys.readouterr()
    assert "Inalteradas: 2" in captured_2.out
    assert "Nenhuma entidade pendente de análise" in captured_2.out
    assert "Geração de relatórios concluída com sucesso" in captured_2.out
