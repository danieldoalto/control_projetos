"""Testes automatizados para o módulo de Discovery."""

from pathlib import Path
import pytest

from ctrl_prj.discovery import (
    DiscoveredEntity,
    Manifest,
    ProjectExplorer,
    discover_entities,
    is_project_directory,
    read_manifest,
)


def test_read_manifest_valid(tmp_path):
    """Testa leitura de .ctrl_prj válido com comentários, espaços e campos."""
    manifest_file = tmp_path / ".ctrl_prj"
    manifest_file.write_text(
        """
# Comentário inicial
type = project
name = Meu Super Projeto
depth = 2
""",
        encoding="utf-8",
    )

    manifest = read_manifest(tmp_path)
    assert manifest is not None
    assert manifest.type == "project"
    assert manifest.name == "Meu Super Projeto"
    assert manifest.depth == 2


def test_read_manifest_collection(tmp_path):
    """Testa leitura de manifesto de coleção."""
    manifest_file = tmp_path / ".ctrl_prj"
    manifest_file.write_text(
        """
type=collection
depth=3
""",
        encoding="utf-8",
    )

    manifest = read_manifest(manifest_file)
    assert manifest is not None
    assert manifest.type == "collection"
    assert manifest.depth == 3


def test_read_manifest_non_existent(tmp_path):
    """Testa leitura quando .ctrl_prj não existe."""
    manifest = read_manifest(tmp_path / "inexistente")
    assert manifest is None


def test_heuristics_project_markers(tmp_path):
    """Testa heurísticas com marcadores padrão de projeto."""
    p_python = tmp_path / "proj_py"
    p_python.mkdir()
    (p_python / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert is_project_directory(p_python)

    p_rust = tmp_path / "proj_rust"
    p_rust.mkdir()
    (p_rust / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
    assert is_project_directory(p_rust)

    p_node = tmp_path / "proj_node"
    p_node.mkdir()
    (p_node / "package.json").write_text("{}", encoding="utf-8")
    assert is_project_directory(p_node)


def test_heuristics_code_and_readme(tmp_path):
    """Testa heurística com README e arquivo de código."""
    p_mix = tmp_path / "proj_mix"
    p_mix.mkdir()
    (p_mix / "README.md").write_text("# Doc\n", encoding="utf-8")
    (p_mix / "script.py").write_text("print(1)\n", encoding="utf-8")
    assert is_project_directory(p_mix)


def test_heuristics_empty_or_text_only(tmp_path):
    """Testa diretório sem código ou apenas com arquivos de texto."""
    empty_dir = tmp_path / "vazio"
    empty_dir.mkdir()
    assert not is_project_directory(empty_dir)

    notes_dir = tmp_path / "notas"
    notes_dir.mkdir()
    (notes_dir / "anotacoes.txt").write_text("texto\n", encoding="utf-8")
    assert not is_project_directory(notes_dir)


def test_discovery_boundary_rule_and_exclusions(tmp_path):
    """Garante que subpastas de um projeto não viram novas entidades e exclusões são ignoradas."""
    root = tmp_path / "workspace"
    root.mkdir()

    # Projeto principal
    app = root / "meu_app"
    app.mkdir()
    (app / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    # Subdiretórios do projeto (devem pertencer ao projeto e NÃO virar entidades filhas)
    src = app / "src"
    src.mkdir()
    (src / "main.py").write_text("print('main')\n", encoding="utf-8")
    tests = app / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text("def test(): pass\n", encoding="utf-8")

    # Diretório excluído dentro do app (ex: .venv com código Python dentro)
    venv = app / ".venv"
    venv.mkdir()
    (venv / "site_package.py").write_text("# lib\n", encoding="utf-8")

    # Diretório excluído na raiz (ex: .git)
    git_dir = root / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("", encoding="utf-8")

    entities = discover_entities([root])
    assert len(entities) == 1
    assert entities[0].name == "meu_app"
    assert entities[0].path == app.resolve()
    assert entities[0].type == "project"
    assert entities[0].explicit is False


def test_discovery_explicit_manifest_precedence(tmp_path):
    """Verifica que .ctrl_prj tem precedência sobre heurística."""
    root = tmp_path / "repos"
    root.mkdir()

    custom_proj = root / "custom_dir"
    custom_proj.mkdir()
    # Cria arquivo que indicaria node por heurística, mas .ctrl_prj força script
    (custom_proj / "package.json").write_text("{}", encoding="utf-8")
    (custom_proj / ".ctrl_prj").write_text("type=script\nname=Meu Utilitario\n", encoding="utf-8")

    entities = discover_entities([root])
    assert len(entities) == 1
    assert entities[0].name == "Meu Utilitario"
    assert entities[0].type == "script"
    assert entities[0].explicit is True


def test_discovery_collection_depth(tmp_path):
    """Verifica que uma coleção descobre projetos dentro dela até o depth configurado."""
    root = tmp_path / "roots"
    root.mkdir()

    col = root / "colecao_projetos"
    col.mkdir()
    (col / ".ctrl_prj").write_text("type=collection\ndepth=1\n", encoding="utf-8")

    sub1 = col / "sub1"
    sub1.mkdir()
    (sub1 / "Cargo.toml").write_text("[package]\n", encoding="utf-8")

    sub2 = col / "sub2"
    sub2.mkdir()
    (sub2 / "package.json").write_text("{}", encoding="utf-8")

    entities = discover_entities([root])
    assert len(entities) == 2
    paths = {e.path for e in entities}
    assert paths == {sub1.resolve(), sub2.resolve()}


def test_discovery_multiple_roots(tmp_path):
    """Testa descoberta em múltiplas raízes simultâneas."""
    root1 = tmp_path / "root1"
    root1.mkdir()
    p1 = root1 / "p1"
    p1.mkdir()
    (p1 / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    root2 = tmp_path / "root2"
    root2.mkdir()
    p2 = root2 / "p2"
    p2.mkdir()
    (p2 / "Cargo.toml").write_text("[package]\n", encoding="utf-8")

    entities = discover_entities([root1, root2])
    assert len(entities) == 2
    assert {e.name for e in entities} == {"p1", "p2"}


def test_discovery_root_directory_not_treated_as_leaf_project(tmp_path):
    """Garante que a própria raiz com arquivos soltos não engula subprojetos."""
    root = tmp_path / "MeusProjetos"
    root.mkdir()
    # Arquivo solto na raiz
    (root / "README.md").write_text("# Minha colecao\n", encoding="utf-8")
    (root / "script_aux.py").write_text("print('aux')\n", encoding="utf-8")

    # Subprojetos reais
    sub_proj1 = root / "App1"
    sub_proj1.mkdir()
    (sub_proj1 / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    sub_proj2 = root / "App2"
    sub_proj2.mkdir()
    (sub_proj2 / "package.json").write_text("{}", encoding="utf-8")

    entities = discover_entities([root])
    assert len(entities) == 2
    paths = {e.path for e in entities}
    assert paths == {sub_proj1.resolve(), sub_proj2.resolve()}

