"""Testes para a camada de persistência SQLite (Memory)."""

from pathlib import Path
import sqlite3
import pytest

from ctrl_prj.memory import (
    AnalysisRecord,
    AnalysisRepository,
    Database,
    EntityRecord,
    EntityRepository,
    FileRecord,
    FileRepository,
    HistoryRecord,
    HistoryRepository,
    MemoryManager,
    RootRecord,
    RootRepository,
    SCHEMA_VERSION,
    get_schema_version,
    init_db,
)


@pytest.fixture
def memory_db():
    """Fixture de banco em memória para testes isolados."""
    db = Database(":memory:")
    return db


def test_database_initialization_in_file(tmp_path):
    """Garante que o banco cria diretórios pais e inicializa tabelas em arquivo físico."""
    db_file = tmp_path / "subdir" / "test_ctrl.db"
    db = Database(db_file)
    assert db_file.exists()

    with db.get_connection() as conn:
        ver = get_schema_version(conn)
        assert ver == SCHEMA_VERSION


def test_schema_init_idempotency(memory_db):
    """Garante que rodar init_db múltiplas vezes não causa erro."""
    with memory_db.get_connection() as conn:
        init_db(conn)
        init_db(conn)
        assert get_schema_version(conn) == SCHEMA_VERSION


def test_roots_repository_crud(memory_db):
    """Testa operações de inserção, busca e listagem de raízes."""
    with memory_db.get_connection() as conn:
        repo = RootRepository(conn)
        
        root1 = repo.get_or_create("/home/user/projetos")
        assert root1.id is not None
        assert root1.path == "/home/user/projetos"

        # get_or_create idempotente
        root1_again = repo.get_or_create("/home/user/projetos")
        assert root1_again.id == root1.id

        root2 = repo.get_or_create("/home/user/scripts")
        all_roots = repo.list_all()
        assert len(all_roots) == 2
        assert {r.path for r in all_roots} == {"/home/user/projetos", "/home/user/scripts"}

        by_path = repo.get_by_path("/home/user/scripts")
        assert by_path is not None
        assert by_path.id == root2.id


def test_entities_repository_crud(memory_db):
    """Testa criação, upsert e atualização de status de entidades."""
    with memory_db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)

        root = root_repo.get_or_create("/home/user/projetos")

        entity = EntityRecord(
            root_id=root.id,
            path="/home/user/projetos/meu_app",
            name="meu_app",
            type="project",
            status="new",
            fingerprint="hash_v1",
        )

        saved = entity_repo.upsert(entity)
        assert saved.id is not None
        assert saved.name == "meu_app"
        assert saved.status == "new"

        # Upsert para modificar
        entity.fingerprint = "hash_v2"
        entity.status = "changed"
        updated = entity_repo.upsert(entity)
        assert updated.id == saved.id
        assert updated.fingerprint == "hash_v2"
        assert updated.status == "changed"

        # Listagem por status
        changed_list = entity_repo.list_by_status("changed")
        assert len(changed_list) == 1
        assert changed_list[0].id == saved.id

        # Update de status pontual
        assert entity_repo.update_status(saved.id, "analyzed")
        by_id = entity_repo.get_by_id(saved.id)
        assert by_id.status == "analyzed"


def test_files_repository_crud_and_bulk(memory_db):
    """Testa inserção e bulk upsert de arquivos associados a entidades."""
    with memory_db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        file_repo = FileRepository(conn)

        root = root_repo.get_or_create("/home/user/projetos")
        entity = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,
                path="/home/user/projetos/meu_app",
                name="meu_app",
                type="project",
            )
        )

        files = [
            FileRecord(
                entity_id=entity.id,
                relative_path="src/main.py",
                file_hash="hash_main",
                size_bytes=1024,
                lines_count=50,
                language="python",
                is_code=True,
            ),
            FileRecord(
                entity_id=entity.id,
                relative_path="README.md",
                file_hash="hash_readme",
                size_bytes=512,
                lines_count=20,
                language="markdown",
                is_context=True,
            ),
            FileRecord(
                entity_id=entity.id,
                relative_path="temp.py",
                file_hash="hash_temp",
                size_bytes=100,
                lines_count=5,
                language="python",
                is_code=True,
            ),
        ]

        file_repo.bulk_upsert(files)
        saved_files = file_repo.list_by_entity(entity.id)
        assert len(saved_files) == 3

        # Remoção de arquivos ausentes (apaga temp.py)
        active_paths = ["src/main.py", "README.md"]
        deleted_count = file_repo.delete_missing_in_entity(entity.id, active_paths)
        assert deleted_count == 1

        remaining = file_repo.list_by_entity(entity.id)
        assert len(remaining) == 2
        assert {f.relative_path for f in remaining} == {"src/main.py", "README.md"}


def test_analyses_repository_crud(memory_db):
    """Testa armazenamento e recuperação de análises LLM."""
    with memory_db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        analysis_repo = AnalysisRepository(conn)

        root = root_repo.get_or_create("/home/user/projetos")
        entity = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,
                path="/home/user/projetos/meu_app",
                name="meu_app",
                type="project",
            )
        )

        analysis1 = AnalysisRecord(
            entity_id=entity.id,
            name="Meu App",
            type="cli",
            description="CLI de automação",
            purpose="Automatizar tarefas",
            languages_json='["Python"]',
            technologies_json='["argparse"]',
            confidence=0.95,
            raw_response='{"name": "Meu App"}',
            entity_fingerprint="hash_v1",
        )
        saved1 = analysis_repo.create(analysis1)
        assert saved1.id is not None

        analysis2 = AnalysisRecord(
            entity_id=entity.id,
            name="Meu App Atualizado",
            type="cli",
            description="CLI avançada de automação",
            purpose="Automatizar tarefas complexas",
            languages_json='["Python"]',
            technologies_json='["argparse", "pydantic"]',
            confidence=0.98,
            raw_response='{"name": "Meu App Atualizado"}',
            entity_fingerprint="hash_v2",
        )
        saved2 = analysis_repo.create(analysis2)

        latest = analysis_repo.get_latest_by_entity(entity.id)
        assert latest is not None
        assert latest.id == saved2.id
        assert latest.name == "Meu App Atualizado"

        all_analyses = analysis_repo.list_by_entity(entity.id)
        assert len(all_analyses) == 2


def test_history_repository_and_set_null(memory_db):
    """Testa auditoria no histórico e preservação de registro após exclusão de entidade."""
    with memory_db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        history_repo = HistoryRepository(conn)

        root = root_repo.get_or_create("/home/user/projetos")
        entity = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,
                path="/home/user/projetos/meu_app",
                name="meu_app",
                type="project",
            )
        )

        hist = history_repo.create(
            HistoryRecord(
                entity_id=entity.id,
                entity_path=entity.path,
                event_type="ADDED",
                fingerprint_before=None,
                fingerprint_after="hash_initial",
                details_json='{"files_count": 2}',
            )
        )
        assert hist.id is not None
        assert hist.event_type == "ADDED"

        # Deleta a entidade
        entity_repo.delete(entity.id)

        # Histórico deve persistir, com entity_id definido como NULL (ON DELETE SET NULL)
        persisted_hist = history_repo.get_by_id(hist.id)
        assert persisted_hist is not None
        assert persisted_hist.entity_id is None
        assert persisted_hist.entity_path == "/home/user/projetos/meu_app"


def test_foreign_key_cascade_delete(memory_db):
    """Garante que a deleção de uma raiz ou entidade remove seus filhos em cascata."""
    with memory_db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)
        file_repo = FileRepository(conn)
        analysis_repo = AnalysisRepository(conn)

        root = root_repo.get_or_create("/home/user/projetos")
        entity = entity_repo.upsert(
            EntityRecord(
                root_id=root.id,
                path="/home/user/projetos/meu_app",
                name="meu_app",
                type="project",
            )
        )

        file_repo.upsert(
            FileRecord(
                entity_id=entity.id,
                relative_path="main.py",
                file_hash="h1",
                size_bytes=100,
            )
        )

        analysis_repo.create(
            AnalysisRecord(
                entity_id=entity.id,
                name="App",
                type="application",
                description="desc",
                entity_fingerprint="h1",
            )
        )

        # Deletando a raiz deve deletar em cascata a entidade, seus arquivos e análises
        assert root_repo.delete(root.id)
        assert entity_repo.get_by_id(entity.id) is None
        assert len(file_repo.list_by_entity(entity.id)) == 0
        assert analysis_repo.get_latest_by_entity(entity.id) is None


def test_memory_manager_integration(memory_db):
    """Testa o orquestrador MemoryManager com todas as operações integradas."""
    manager = MemoryManager(memory_db)
    with manager.get_connection() as conn:
        root = manager.roots(conn).get_or_create("/tmp/root")
        entity = manager.entities(conn).upsert(
            EntityRecord(root_id=root.id, path="/tmp/root/app", name="app")
        )
        manager.files(conn).upsert(
            FileRecord(entity_id=entity.id, relative_path="app.py", file_hash="h123")
        )
        manager.analyses(conn).create(
            AnalysisRecord(
                entity_id=entity.id,
                name="app",
                type="script",
                description="desc",
                entity_fingerprint="h123",
            )
        )
        manager.history(conn).create(
            HistoryRecord(entity_id=entity.id, entity_path=entity.path, event_type="ADDED")
        )

        assert len(manager.entities(conn).list_all()) == 1
        assert len(manager.files(conn).list_by_entity(entity.id)) == 1
        assert len(manager.history(conn).list_by_entity(entity.id)) == 1
