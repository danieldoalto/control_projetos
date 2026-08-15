"""Testes automatizados para o módulo de Hash e Fingerprint."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from ctrl_prj.fingerprint import (
    HashedFile,
    MacroStatus,
    calculate_entity_fingerprint,
    compare_entity_state,
    hash_bytes,
    hash_file,
    hash_scanned_files,
)
from ctrl_prj.memory import Database, EntityRecord, EntityRepository, RootRepository
from ctrl_prj.scanner import ScannedFile


def test_hash_file_and_bytes(tmp_path):
    """Testa cálculo de hash SHA-256 para arquivos e arrays de bytes."""
    content = b"print('hello world')\n"
    f1 = tmp_path / "f1.py"
    f2 = tmp_path / "f2.py"
    f1.write_bytes(content)
    f2.write_bytes(content)

    h1 = hash_file(f1)
    h2 = hash_file(f2)
    h_bytes = hash_bytes(content)

    assert h1 == h2 == h_bytes
    assert len(h1) == 64  # SHA-256 hex string

    # Arquivo com conteúdo diferente gera hash diferente
    f3 = tmp_path / "f3.py"
    f3.write_bytes(b"print('outro conteudo')\n")
    assert hash_file(f3) != h1


def test_hash_empty_file(tmp_path):
    """Testa hash de arquivo vazio (SHA-256 padrão de 0 bytes)."""
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    # SHA-256 de vazio
    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert hash_file(empty) == expected


def test_calculate_entity_fingerprint_determinism():
    """Garante que a ordem dos arquivos na lista não altera o fingerprint final da entidade."""
    file_a = HashedFile(
        path=Path("/proj/a.py"),
        relative_path="a.py",
        file_hash="hash_a",
        extension=".py",
        file_type="code",
        is_code=True,
        is_context=False,
        size_bytes=100,
        mtime=1.0,
    )
    file_b = HashedFile(
        path=Path("/proj/src/b.py"),
        relative_path="src/b.py",
        file_hash="hash_b",
        extension=".py",
        file_type="code",
        is_code=True,
        is_context=False,
        size_bytes=200,
        mtime=1.0,
    )
    file_c = HashedFile(
        path=Path("/proj/README.md"),
        relative_path="README.md",
        file_hash="hash_c",
        extension=".md",
        file_type="context",
        is_code=False,
        is_context=True,
        size_bytes=50,
        mtime=1.0,
    )

    # Listas com ordens distintas
    fp1 = calculate_entity_fingerprint([file_a, file_b, file_c])
    fp2 = calculate_entity_fingerprint([file_c, file_a, file_b])
    fp3 = calculate_entity_fingerprint([file_b, file_c, file_a])

    assert fp1 == fp2 == fp3
    assert len(fp1) == 64


def test_calculate_entity_fingerprint_changes_on_file_modification():
    """Garante que qualquer alteração de arquivo altera o fingerprint da entidade."""
    file_a = HashedFile(
        path=Path("/proj/a.py"),
        relative_path="a.py",
        file_hash="hash_a_v1",
        extension=".py",
        file_type="code",
        is_code=True,
        is_context=False,
        size_bytes=100,
        mtime=1.0,
    )
    fp_v1 = calculate_entity_fingerprint([file_a])

    file_a_modified = HashedFile(
        path=Path("/proj/a.py"),
        relative_path="a.py",
        file_hash="hash_a_v2",
        extension=".py",
        file_type="code",
        is_code=True,
        is_context=False,
        size_bytes=110,
        mtime=2.0,
    )
    fp_v2 = calculate_entity_fingerprint([file_a_modified])

    assert fp_v1 != fp_v2


def test_hash_scanned_files_integration(tmp_path):
    """Testa integração com a lista de ScannedFile."""
    f1 = tmp_path / "app.py"
    f1.write_text("code\n", encoding="utf-8")
    scanned = [
        ScannedFile(
            path=f1,
            relative_path="app.py",
            extension=".py",
            file_type="code",
            is_code=True,
            is_context=False,
            size_bytes=5,
            mtime=100.0,
            language="python",
        )
    ]
    hashed_list = hash_scanned_files(scanned)
    assert len(hashed_list) == 1
    assert hashed_list[0].file_hash == hash_file(f1)


def test_compare_entity_state_with_mock():
    """Testa a lógica do comparador com mock do EntityRepository."""
    mock_repo = MagicMock(spec=EntityRepository)

    # Caso 1: NEW (entidade não existe no banco)
    mock_repo.get_by_path.return_value = None
    status = compare_entity_state("/path/to/new_proj", "fp_123", mock_repo)
    assert status == MacroStatus.NEW
    assert status == "new"

    # Caso 2: UNCHANGED (fingerprint igual ao gravado)
    mock_repo.get_by_path.return_value = EntityRecord(
        id=1,
        root_id=1,
        path=str(Path("/path/to/existing_proj").resolve()),
        name="existing_proj",
        fingerprint="fp_123",
    )
    status_unchanged = compare_entity_state(
        "/path/to/existing_proj", "fp_123", mock_repo
    )
    assert status_unchanged == MacroStatus.UNCHANGED
    assert status_unchanged == "unchanged"

    # Caso 3: CHANGED (fingerprint diferente do gravado)
    mock_repo.get_by_path.return_value = EntityRecord(
        id=1,
        root_id=1,
        path=str(Path("/path/to/existing_proj").resolve()),
        name="existing_proj",
        fingerprint="fp_antigo",
    )
    status_changed = compare_entity_state(
        "/path/to/existing_proj", "fp_novo", mock_repo
    )
    assert status_changed == MacroStatus.CHANGED
    assert status_changed == "changed"


def test_compare_entity_state_with_sqlite_db():
    """Testa o comparador integrado com banco SQLite real em memória."""
    db = Database(":memory:")
    with db.get_connection() as conn:
        root_repo = RootRepository(conn)
        entity_repo = EntityRepository(conn)

        root = root_repo.get_or_create("/work")
        proj_path = str(Path("/work/app").resolve())

        # 1. Antes de inserir no banco -> NEW
        assert compare_entity_state(proj_path, "fp_v1", entity_repo) == MacroStatus.NEW

        # 2. Inserindo no banco com fp_v1
        entity_repo.upsert(
            EntityRecord(
                root_id=root.id,
                path=proj_path,
                name="app",
                fingerprint="fp_v1",
            )
        )

        # Mesma fingerprint -> UNCHANGED
        assert compare_entity_state(proj_path, "fp_v1", entity_repo) == MacroStatus.UNCHANGED

        # Fingerprint alterada -> CHANGED
        assert compare_entity_state(proj_path, "fp_v2", entity_repo) == MacroStatus.CHANGED
