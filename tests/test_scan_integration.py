"""Testes de integração para o comando e orquestrador de Scan."""

import json
from pathlib import Path
import shutil
import pytest

from ctrl_prj.cli import main
from ctrl_prj.config import AppConfig, ScanConfig, DatabaseConfig
from ctrl_prj.memory import Database, EntityRepository, FileRepository, HistoryRepository
from ctrl_prj.scanner import ScanResult, run_scan


def test_scan_full_lifecycle(tmp_path):
    """Testa o ciclo de vida completo: new -> unchanged -> changed -> missing."""
    roots_dir = tmp_path / "projetos"
    roots_dir.mkdir()

    app_dir = roots_dir / "meu_app"
    app_dir.mkdir()
    (app_dir / "pyproject.toml").write_text("[project]\nname = 'meu_app'\n", encoding="utf-8")
    (app_dir / "main.py").write_text("print('v1')\n", encoding="utf-8")

    db_path = tmp_path / "ctrl.db"
    db = Database(db_path)

    config = AppConfig(
        scan=ScanConfig(roots=[roots_dir]),
        database=DatabaseConfig(path=db_path),
    )

    # -------------------------------------------------------------
    # 1º SCAN: Entidade nova (NEW)
    # -------------------------------------------------------------
    res1: ScanResult = run_scan(config, db)
    assert res1.roots_scanned == 1
    assert res1.total_entities == 1
    assert res1.new_count == 1
    assert res1.changed_count == 0
    assert res1.unchanged_count == 0
    assert res1.missing_count == 0
    assert res1.total_files == 2

    with db.get_connection() as conn:
        entity_repo = EntityRepository(conn)
        file_repo = FileRepository(conn)
        history_repo = HistoryRepository(conn)

        entities = entity_repo.list_all()
        assert len(entities) == 1
        assert entities[0].name == "meu_app"
        assert entities[0].status == "new"
        assert entities[0].fingerprint is not None

        files = file_repo.list_by_entity(entities[0].id)
        assert len(files) == 2
        assert {f.relative_path for f in files} == {"main.py", "pyproject.toml"}

        hist = history_repo.list_by_entity(entities[0].id)
        assert len(hist) == 1
        assert hist[0].event_type == "ADDED"

    # -------------------------------------------------------------
    # 2º SCAN: Sem modificações (UNCHANGED)
    # -------------------------------------------------------------
    res2: ScanResult = run_scan(config, db)
    assert res2.total_entities == 1
    assert res2.new_count == 0
    assert res2.changed_count == 0
    assert res2.unchanged_count == 1
    assert res2.missing_count == 0

    # -------------------------------------------------------------
    # 3º SCAN: Modificação de arquivos (CHANGED)
    # Modifica main.py, adiciona helper.py e remove pyproject.toml
    # (adicionamos .ctrl_prj para continuar sendo projeto explícito após remover pyproject)
    # -------------------------------------------------------------
    (app_dir / ".ctrl_prj").write_text("type=project\n", encoding="utf-8")
    (app_dir / "main.py").write_text("print('v2 modificado')\n", encoding="utf-8")
    (app_dir / "helper.py").write_text("def help(): pass\n", encoding="utf-8")
    (app_dir / "pyproject.toml").unlink()

    res3: ScanResult = run_scan(config, db)
    assert res3.total_entities == 1
    assert res3.new_count == 0
    assert res3.changed_count == 1
    assert res3.unchanged_count == 0

    with db.get_connection() as conn:
        entity_repo = EntityRepository(conn)
        file_repo = FileRepository(conn)
        history_repo = HistoryRepository(conn)

        entities = entity_repo.list_all()
        assert entities[0].status == "changed"

        files = file_repo.list_by_entity(entities[0].id)
        # Arquivos atuais no disco: helper.py, main.py (.ctrl_prj não é código nem contexto)
        assert {f.relative_path for f in files} == {"helper.py", "main.py"}

        hist = history_repo.list_by_entity(entities[0].id)
        assert len(hist) == 2
        assert hist[0].event_type == "MODIFIED"  # mais recente no topo
        details = json.loads(hist[0].details_json)
        assert details["added"] == 1    # helper.py
        assert details["modified"] == 1 # main.py
        assert details["deleted"] == 1  # pyproject.toml

    # -------------------------------------------------------------
    # 4º SCAN: Entidade deletada do disco (MISSING)
    # -------------------------------------------------------------
    shutil.rmtree(app_dir)

    res4: ScanResult = run_scan(config, db)
    assert res4.total_entities == 0
    assert res4.missing_count == 1

    with db.get_connection() as conn:
        entity_repo = EntityRepository(conn)
        history_repo = HistoryRepository(conn)

        entities = entity_repo.list_all()
        # Entidade não é apagada da base!
        assert len(entities) == 1
        assert entities[0].status == "missing"

        hist = history_repo.list_by_entity(entities[0].id)
        assert len(hist) == 3
        assert hist[0].event_type == "MISSING"


def test_cli_scan_command_execution(tmp_path, capsys):
    """Testa execução do comando scan via CLI com config temporário."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    p1 = workspace / "p1"
    p1.mkdir()
    (p1 / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (p1 / "main.py").write_text("print('hi')\n", encoding="utf-8")

    db_file = tmp_path / "cli_test.db"
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        f"""
scan:
  roots:
    - "{workspace.as_posix()}"
database:
  path: "{db_file.as_posix()}"
""",
        encoding="utf-8",
    )

    exit_code = main(["-c", str(config_file), "scan"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Iniciando varredura" in captured.out
    assert "Total de entidades encontradas: 1" in captured.out
    assert "✨ Novas: 1" in captured.out
    assert "Varredura concluída com sucesso." in captured.out
    assert db_file.exists()


def test_cli_scan_without_roots(tmp_path, capsys):
    """Testa comportamento da CLI quando não há roots nem individual_projects configurados."""
    config_file = tmp_path / "empty_roots_config.yml"
    config_file.write_text("scan:\n  roots: []\n  individual_projects: []\n", encoding="utf-8")

    exit_code = main(["-c", str(config_file), "scan"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Nenhuma raiz" in captured.out


def test_scan_with_individual_projects(tmp_path):
    """Testa scan combinando roots e individual_projects (diretório e script isolado)."""
    # 1. Raiz contêiner com 1 projeto
    roots_dir = tmp_path / "container_root"
    roots_dir.mkdir()
    p1 = roots_dir / "p1"
    p1.mkdir()
    (p1 / "pyproject.toml").write_text("[project]\nname = 'p1'\n", encoding="utf-8")

    # 2. Projeto individual em pasta isolada
    indiv_proj = tmp_path / "standalone_project"
    indiv_proj.mkdir()
    (indiv_proj / "README.md").write_text("# Standalone Project\n", encoding="utf-8")
    (indiv_proj / "app.py").write_text("print('standalone')\n", encoding="utf-8")

    # 3. Script individual avulso
    script_file = tmp_path / "scripts" / "backup.sh"
    script_file.parent.mkdir()
    script_file.write_text("#!/bin/bash\necho backup\n", encoding="utf-8")

    db_path = tmp_path / "test_indiv.db"
    db = Database(db_path)

    config = AppConfig(
        scan=ScanConfig(
            roots=[roots_dir],
            individual_projects=[indiv_proj, script_file],
        ),
        database=DatabaseConfig(path=db_path),
    )

    res = run_scan(config, db)
    assert res.total_entities == 3
    assert res.new_count == 3

    with db.get_connection() as conn:
        entity_repo = EntityRepository(conn)
        entities = entity_repo.list_all()
        assert len(entities) == 3
        names = {e.name for e in entities}
        assert "p1" in names
        assert "standalone_project" in names
        assert "backup" in names
        types = {e.name: e.type for e in entities}
        assert types["backup"] == "script"
        assert types["standalone_project"] == "project"

