"""Testes para o cálculo de deltas de arquivos (FileDelta)."""

from pathlib import Path
import pytest

from ctrl_prj.fingerprint import FileDelta, HashedFile, compute_file_delta
from ctrl_prj.memory import FileRecord


def test_compute_file_delta_all_categories():
    """Testa cálculo de deltas com arquivos adicionados, modificados, deletados e inalterados."""
    # Arquivos atualmente no disco
    current_files = [
        # Inalterado
        HashedFile(
            path=Path("/app/unchanged.py"),
            relative_path="unchanged.py",
            file_hash="hash_same",
            extension=".py",
            file_type="code",
            is_code=True,
            is_context=False,
            size_bytes=100,
            mtime=1.0,
            language="python",
        ),
        # Modificado
        HashedFile(
            path=Path("/app/modified.py"),
            relative_path="modified.py",
            file_hash="hash_new_content",
            extension=".py",
            file_type="code",
            is_code=True,
            is_context=False,
            size_bytes=150,
            mtime=2.0,
            language="python",
        ),
        # Adicionado
        HashedFile(
            path=Path("/app/added.py"),
            relative_path="added.py",
            file_hash="hash_added",
            extension=".py",
            file_type="code",
            is_code=True,
            is_context=False,
            size_bytes=80,
            mtime=3.0,
            language="python",
        ),
    ]

    # Arquivos previamente gravados no banco
    previous_files = [
        # Inalterado
        FileRecord(
            id=1,
            entity_id=1,
            relative_path="unchanged.py",
            file_hash="hash_same",
            size_bytes=100,
        ),
        # Modificado anteriormente com outro hash
        FileRecord(
            id=2,
            entity_id=1,
            relative_path="modified.py",
            file_hash="hash_old_content",
            size_bytes=120,
        ),
        # Deletado (não está mais em current_files)
        FileRecord(
            id=3,
            entity_id=1,
            relative_path="deleted.py",
            file_hash="hash_deleted",
            size_bytes=50,
        ),
    ]

    delta: FileDelta = compute_file_delta(current_files, previous_files)

    assert delta.has_changes is True

    # Added
    assert len(delta.added) == 1
    assert delta.added[0].relative_path == "added.py"

    # Modified
    assert len(delta.modified) == 1
    assert delta.modified[0].relative_path == "modified.py"

    # Deleted
    assert len(delta.deleted) == 1
    assert delta.deleted[0].relative_path == "deleted.py"

    # Unchanged
    assert len(delta.unchanged) == 1
    assert delta.unchanged[0].relative_path == "unchanged.py"

    # Summary
    assert delta.summary_dict == {
        "added": 1,
        "modified": 1,
        "deleted": 1,
        "unchanged": 1,
    }


def test_compute_file_delta_no_changes():
    """Testa cálculo de delta quando nenhum arquivo foi alterado."""
    curr = [
        HashedFile(
            path=Path("/app/main.py"),
            relative_path="main.py",
            file_hash="h1",
            extension=".py",
            file_type="code",
            is_code=True,
            is_context=False,
            size_bytes=10,
            mtime=1.0,
        )
    ]
    prev = [
        FileRecord(
            id=1,
            entity_id=1,
            relative_path="main.py",
            file_hash="h1",
            size_bytes=10,
        )
    ]

    delta = compute_file_delta(curr, prev)
    assert delta.has_changes is False
    assert len(delta.unchanged) == 1
    assert len(delta.added) == 0
    assert len(delta.modified) == 0
    assert len(delta.deleted) == 0
