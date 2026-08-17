"""Testes automatizados para o FileScanner."""

import os
from pathlib import Path
import pytest

from ctrl_prj.scanner import FileScanner, ScannedFile, scan_entity_files


def test_scan_entity_files_filtering(tmp_path):
    """Testa inclusão de arquivos de código/contexto e exclusão de binários, imagens e pastas ignoradas."""
    project_dir = tmp_path / "meu_projeto"
    project_dir.mkdir()

    # Arquivos válidos de código
    (project_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
    src_dir = project_dir / "src"
    src_dir.mkdir()
    (src_dir / "utils.rs").write_text("fn main() {}\n", encoding="utf-8")
    (src_dir / "script.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    # Arquivos válidos de contexto
    (project_dir / "README.md").write_text("# Meu Projeto\n", encoding="utf-8")
    (project_dir / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (project_dir / "Dockerfile").write_text("FROM alpine\n", encoding="utf-8")
    (project_dir / "Makefile").write_text("all:\n\t@echo ok\n", encoding="utf-8")

    # Arquivos ignorados (imagens, binários, compactados, temporários)
    (project_dir / "foto.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (project_dir / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftyp")
    (project_dir / "pacote.zip").write_bytes(b"PK\x03\x04")
    (project_dir / "compilado.pyc").write_bytes(b"\x00\x00")
    (project_dir / ".DS_Store").write_bytes(b"\x00")
    (project_dir / "temp.tmp").write_text("temp", encoding="utf-8")

    # Diretórios excluídos por padrão (.venv, node_modules, .git)
    venv_dir = project_dir / ".venv"
    venv_dir.mkdir()
    (venv_dir / "lib.py").write_text("# venv lib", encoding="utf-8")

    node_dir = project_dir / "node_modules"
    node_dir.mkdir()
    (node_dir / "package.js").write_text("console.log(1)", encoding="utf-8")

    files = scan_entity_files(project_dir)

    rel_paths = [f.relative_path for f in files]
    expected_rel_paths = [
        "Dockerfile",
        "Makefile",
        "README.md",
        "main.py",
        "pyproject.toml",
        "src/script.sh",
        "src/utils.rs",
    ]

    assert sorted(rel_paths) == sorted(expected_rel_paths)


def test_scanned_file_metadata_and_classification(tmp_path):
    """Garante que os metadados de tamanho, mtime e classificação de tipo estejam corretos."""
    project_dir = tmp_path / "metadata_test"
    project_dir.mkdir()

    py_content = "def add(a, b):\n    return a + b\n"
    py_file = project_dir / "calc.py"
    py_file.write_text(py_content, encoding="utf-8")

    doc_file = project_dir / "README.md"
    doc_file.write_text("# Docs\n", encoding="utf-8")

    scanner = FileScanner()
    files = scanner.scan_entity(project_dir)

    file_by_name = {f.relative_path: f for f in files}

    # Verifica calc.py
    py_scanned = file_by_name["calc.py"]
    assert py_scanned.path == py_file.resolve()
    assert py_scanned.extension == ".py"
    assert py_scanned.language == "python"
    assert py_scanned.is_code is True
    assert py_scanned.is_context is False
    assert py_scanned.file_type == "code"
    assert py_scanned.size_bytes == py_file.stat().st_size
    assert py_scanned.mtime > 0

    # Verifica README.md
    doc_scanned = file_by_name["README.md"]
    assert doc_scanned.path == doc_file.resolve()
    assert doc_scanned.extension == ".md"
    assert doc_scanned.language == "markdown"
    assert doc_scanned.is_code is False
    assert doc_scanned.is_context is True
    assert doc_scanned.file_type == "context"


def test_scan_symlinks_ignored(tmp_path):
    """Garante que symlinks não são seguidos quando follow_symlinks=False."""
    project_dir = tmp_path / "symlink_test"
    project_dir.mkdir()

    real_file = tmp_path / "outside.py"
    real_file.write_text("print('outside')\n", encoding="utf-8")

    symlink_file = project_dir / "link_inside.py"
    try:
        symlink_file.symlink_to(real_file)
    except OSError:
        pytest.skip("Symlinks não suportados no filesystem atual")

    scanner = FileScanner(follow_symlinks=False)
    files = scanner.scan_entity(project_dir)
    assert len(files) == 0


def test_scan_single_file_script(tmp_path):
    """Testa escaneamento de um arquivo individual (script isolado)."""
    script_path = tmp_path / "deploy.sh"
    script_path.write_text("#!/bin/bash\necho deploying...\n", encoding="utf-8")

    files = scan_entity_files(script_path)
    assert len(files) == 1
    scanned = files[0]
    assert scanned.relative_path == "deploy.sh"
    assert scanned.extension == ".sh"
    assert scanned.language == "bash"
    assert scanned.is_code is True


def test_scan_non_existent_entity():
    """Garante retorno vazio para entidades inexistentes."""
    files = scan_entity_files(Path("/caminho/completamente/inexistente/xyz"))
    assert files == []


def test_scan_permission_denied_directory(tmp_path):
    """Garante que diretórios ou arquivos inacessíveis (PermissionError) são ignorados sem falhar."""
    import os
    project_dir = tmp_path / "proj_with_restricted_subdir"
    project_dir.mkdir()
    (project_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")

    restricted_subdir = project_dir / "restricted_ts_state"
    restricted_subdir.mkdir()
    (restricted_subdir / "secret.py").write_text("print('secret')\n", encoding="utf-8")

    try:
        # Remove permissão de leitura
        os.chmod(restricted_subdir, 0o000)
        scanner = FileScanner()
        files = scanner.scan_entity(project_dir)
        # O arquivo main.py deve ser escaneado e o diretório restrito ignorado
        assert any(f.relative_path == "main.py" for f in files)
    finally:
        # Restaura permissão para limpeza do tmp_path
        os.chmod(restricted_subdir, 0o755)

