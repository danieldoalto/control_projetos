"""Testes de integração para o orquestrador de análise (Analyze Orchestrator)."""

import json
from pathlib import Path
import pytest

from ctrl_prj.analyzer import run_analyze
from ctrl_prj.cli import main
from ctrl_prj.config.settings import AppConfig, LLMConfig
from ctrl_prj.llm.base import LLMProvider
from ctrl_prj.llm.mock_provider import MockProvider
from ctrl_prj.memory import (
    AnalysisRepository,
    Database,
    EntityRecord,
    EntityRepository,
    FileRecord,
    FileRepository,
    RootRecord,
    RootRepository,
)


class FailingMockProvider(LLMProvider):
    """Provedor que falha na primeira entidade e tem sucesso nas demais."""

    def __init__(self, fail_first_n: int = 1):
        self.call_count = 0
        self.fail_first_n = fail_first_n
        self.mock_provider = MockProvider()

    def generate_response(self, prompt: str, system_prompt: str | None = None) -> str:
        self.call_count += 1
        if self.call_count <= self.fail_first_n:
            raise RuntimeError("Falha de conexão com a API do LLM simulada")
        return self.mock_provider.generate_response(prompt, system_prompt)


@pytest.fixture
def temp_workspace(tmp_path: Path):
    """Cria um ambiente temporário com banco SQLite e arquivos de projeto."""
    db_path = tmp_path / "test_data.db"
    db = Database(db_path)

    # Cria diretório de projeto com arquivos reais
    project_dir = tmp_path / "meu_projeto"
    project_dir.mkdir()
    (project_dir / "main.py").write_text(
        "def main():\n    print('Hello World')\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    (project_dir / "README.md").write_text(
        "# Meu Projeto\nUm projeto CLI simples para testes.\n",
        encoding="utf-8",
    )

    config = AppConfig(
        database={"path": str(db_path)},
        llm=LLMConfig(provider="mock"),
        roots=[str(tmp_path)],
    )

    return {
        "tmp_path": tmp_path,
        "db": db,
        "config": config,
        "project_dir": project_dir,
    }


def test_analyze_new_entity_lifecycle(temp_workspace):
    """Testa o ciclo completo de análise de uma entidade nova."""
    db: Database = temp_workspace["db"]
    config: AppConfig = temp_workspace["config"]
    project_dir: Path = temp_workspace["project_dir"]

    # 1. Popula banco com dados simulados do scanner
    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        file_repo = FileRepository(conn)

        root = root_repo.get_or_create(str(temp_workspace["tmp_path"]))
        entity = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,  # type: ignore
                path=str(project_dir),
                name="meu_projeto",
                type="project",
                status="new",
                fingerprint="fp_abc123",
            )
        )

        file_repo.upsert(
            FileRecord(
                entity_id=entity.id,  # type: ignore
                relative_path="main.py",
                file_hash="hash_py",
                size_bytes=100,
                lines_count=5,
                language="python",
                is_code=True,
            )
        )
        file_repo.upsert(
            FileRecord(
                entity_id=entity.id,  # type: ignore
                relative_path="README.md",
                file_hash="hash_md",
                size_bytes=50,
                lines_count=2,
                language=None,
                is_context=True,
            )
        )

    # 2. Executa a análise com MockProvider
    result = run_analyze(config, db, provider=MockProvider())

    assert result.total_pending == 1
    assert result.analyzed_count == 1
    assert result.error_count == 0
    assert len(result.summaries) == 1

    summary = result.summaries[0]
    assert summary.status == "analyzed"
    assert summary.name == "Mock Project"

    # 3. Verifica persistência no SQLite
    with db.get_connection() as conn:
        entity_repo = EntityRepository(conn)
        analysis_repo = AnalysisRepository(conn)

        updated_entity = entity_repo.get_by_id(entity.id)  # type: ignore
        assert updated_entity is not None
        assert updated_entity.status == "analyzed"

        latest_analysis = analysis_repo.get_latest_by_entity(entity.id)  # type: ignore
        assert latest_analysis is not None
        assert latest_analysis.entity_id == entity.id
        assert latest_analysis.name == "Mock Project"
        assert latest_analysis.description != ""
        assert latest_analysis.purpose != ""
        assert latest_analysis.confidence > 0.0


        # Valida JSONs salvos
        langs = json.loads(latest_analysis.languages_json)
        assert isinstance(langs, list)


def test_analyze_incremental_skip(temp_workspace):
    """Testa se entidades já analisadas são ignoradas em execuções incrementais."""
    db: Database = temp_workspace["db"]
    config: AppConfig = temp_workspace["config"]
    project_dir: Path = temp_workspace["project_dir"]

    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        root = root_repo.get_or_create(str(temp_workspace["tmp_path"]))
        entity_repo.upsert(
            EntityRecord(
                root_id=root.id,  # type: ignore
                path=str(project_dir),
                name="meu_projeto",
                type="project",
                status="analyzed",
                fingerprint="fp_abc123",
            )
        )

    result = run_analyze(config, db, provider=MockProvider())

    assert result.total_pending == 0
    assert result.analyzed_count == 0
    assert result.already_analyzed_count == 1
    assert len(result.summaries) == 0


def test_analyze_changed_entity(temp_workspace):
    """Testa reanálise de entidade modificada (status='changed')."""
    db: Database = temp_workspace["db"]
    config: AppConfig = temp_workspace["config"]
    project_dir: Path = temp_workspace["project_dir"]

    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        file_repo = FileRepository(conn)

        root = root_repo.get_or_create(str(temp_workspace["tmp_path"]))
        entity = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,  # type: ignore
                path=str(project_dir),
                name="meu_projeto",
                type="project",
                status="changed",
                fingerprint="fp_abc456",
            )
        )
        file_repo.upsert(
            FileRecord(
                entity_id=entity.id,  # type: ignore
                relative_path="main.py",
                file_hash="hash_py_v2",
                size_bytes=120,
                lines_count=6,
                language="python",
                is_code=True,
            )
        )

    result = run_analyze(config, db, provider=MockProvider())

    assert result.total_pending == 1
    assert result.analyzed_count == 1
    assert result.error_count == 0

    with db.get_connection() as conn:
        entity_repo = EntityRepository(conn)
        updated_entity = entity_repo.get_by_id(entity.id)  # type: ignore
        assert updated_entity.status == "analyzed"


def test_analyze_error_resilience(temp_workspace):
    """Testa se uma falha em uma entidade não interrompe o processamento das outras."""
    db: Database = temp_workspace["db"]
    config: AppConfig = temp_workspace["config"]
    tmp_path: Path = temp_workspace["tmp_path"]

    proj1 = tmp_path / "proj1"
    proj2 = tmp_path / "proj2"
    proj1.mkdir()
    proj2.mkdir()
    (proj1 / "a.py").write_text("x = 1\n", encoding="utf-8")
    (proj2 / "b.py").write_text("y = 2\n", encoding="utf-8")

    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        file_repo = FileRepository(conn)

        root = root_repo.get_or_create(str(tmp_path))
        e1 = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,  # type: ignore
                path=str(proj1),
                name="proj1",
                type="project",
                status="new",
            )
        )
        file_repo.upsert(
            FileRecord(
                entity_id=e1.id,  # type: ignore
                relative_path="a.py",
                file_hash="h1",
                is_code=True,
            )
        )

        e2 = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,  # type: ignore
                path=str(proj2),
                name="proj2",
                type="project",
                status="new",
            )
        )
        file_repo.upsert(
            FileRecord(
                entity_id=e2.id,  # type: ignore
                relative_path="b.py",
                file_hash="h2",
                is_code=True,
            )
        )

    # Usa provider que falha no 1º e tem sucesso no 2º
    failing_provider = FailingMockProvider(fail_first_n=1)
    result = run_analyze(config, db, provider=failing_provider)

    assert result.total_pending == 2
    assert result.analyzed_count == 1
    assert result.error_count == 1

    with db.get_connection() as conn:
        entity_repo = EntityRepository(conn)
        rec1 = entity_repo.get_by_id(e1.id)  # type: ignore
        rec2 = entity_repo.get_by_id(e2.id)  # type: ignore

        assert rec1.status == "error"
        assert rec2.status == "analyzed"


def test_analyze_cli_integration(temp_workspace, capsys):
    """Testa a chamada do comando analyze via CLI."""
    db: Database = temp_workspace["db"]
    config: AppConfig = temp_workspace["config"]
    project_dir: Path = temp_workspace["project_dir"]

    # Cria arquivo de configuração temporário
    config_file = temp_workspace["tmp_path"] / "config.yml"
    db_path_posix = Path(temp_workspace["db"].db_path).as_posix()
    root_posix = Path(temp_workspace["tmp_path"]).as_posix()
    config_file.write_text(
        f"""
database:
  path: "{db_path_posix}"
llm:
  provider: "mock"
roots:
  - "{root_posix}"
""",
        encoding="utf-8",
    )

    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        root = root_repo.get_or_create(str(temp_workspace["tmp_path"]))
        entity_repo.upsert(
            EntityRecord(
                root_id=root.id,  # type: ignore
                path=str(project_dir),
                name="meu_projeto",
                type="project",
                status="new",
            )
        )

    exit_code = main(["-c", str(config_file), "analyze"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Buscando entidades pendentes" in captured.out
    assert "Analisado: meu_projeto" in captured.out
    assert "Resumo da Análise" in captured.out
    assert "Analisadas com sucesso: 1" in captured.out
