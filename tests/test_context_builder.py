"""Testes automatizados para o Construtor de Contexto (ContextBuilder)."""

import json
from pathlib import Path
import pytest

from ctrl_prj.analyzer import LLMContext, build_context
from ctrl_prj.fingerprint.delta import FileDelta
from ctrl_prj.fingerprint.models import HashedFile
from ctrl_prj.memory import AnalysisRecord, EntityRecord, FileRecord


def test_build_context_initial_operation(tmp_path):
    """Testa construção de contexto para operação 'initial' (novo projeto)."""
    proj_dir = tmp_path / "meu_projeto"
    proj_dir.mkdir()

    # Cria arquivo de código
    src_dir = proj_dir / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text(
        """import sys
class Server:
    def start(self): pass
""",
        encoding="utf-8",
    )

    # Cria arquivo de contexto
    (proj_dir / "README.md").write_text("# Meu Projeto Incrivel\nDescricao geral.", encoding="utf-8")

    entity = EntityRecord(
        id=1,
        root_id=1,
        path=str(proj_dir.resolve()),
        name="meu_projeto",
        type="project",
        status="new",
        fingerprint="fp_123",
    )

    files = [
        FileRecord(
            id=1,
            entity_id=1,
            relative_path="src/app.py",
            file_hash="h1",
            is_code=True,
            is_context=False,
            language="python",
        ),
        FileRecord(
            id=2,
            entity_id=1,
            relative_path="README.md",
            file_hash="h2",
            is_code=False,
            is_context=True,
            language="markdown",
        ),
    ]

    ctx: LLMContext = build_context(entity=entity, files=files)

    assert ctx.operation == "initial"
    assert ctx.previous_analysis is None
    assert ctx.changes is None

    # Verifica entity_info
    assert ctx.entity_info["name"] == "meu_projeto"
    assert ctx.entity_info["fingerprint"] == "fp_123"

    # Verifica estrutura de código
    assert "src/app.py" in ctx.file_structure
    app_struct = ctx.file_structure["src/app.py"]
    assert "sys" in app_struct["imports"]
    assert "Server" in app_struct["classes"]
    assert "start" in app_struct["functions"]

    # Verifica conteúdo do contexto
    assert "README.md" in ctx.context_files_content
    assert "Meu Projeto Incrivel" in ctx.context_files_content["README.md"]


def test_build_context_truncates_large_context_files(tmp_path):
    """Testa truncamento seguro de arquivos de contexto grandes para economia de tokens."""
    proj_dir = tmp_path / "large_doc_proj"
    proj_dir.mkdir()

    # Cria README com 500 caracteres
    long_readme = "A" * 500
    (proj_dir / "README.md").write_text(long_readme, encoding="utf-8")

    entity = EntityRecord(
        id=1,
        path=str(proj_dir.resolve()),
        name="large_doc_proj",
        type="project",
    )

    files = [
        FileRecord(
            id=1,
            entity_id=1,
            relative_path="README.md",
            is_code=False,
            is_context=True,
        )
    ]

    # Limita a 100 caracteres
    ctx = build_context(
        entity=entity,
        files=files,
        max_chars_per_context_file=100,
    )

    content = ctx.context_files_content["README.md"]
    assert len(content) < 500
    assert "[conteúdo truncado para economia de tokens]" in content
    assert content.startswith("A" * 100)


def test_build_context_update_operation(tmp_path):
    """Testa construção de contexto para operação 'update' com análise prévia e delta."""
    proj_dir = tmp_path / "update_proj"
    proj_dir.mkdir()
    (proj_dir / "main.py").write_text("def new_func(): pass\n", encoding="utf-8")

    entity = EntityRecord(
        id=1,
        path=str(proj_dir.resolve()),
        name="update_proj",
        type="project",
        status="changed",
        fingerprint="fp_novo",
    )

    files = [
        FileRecord(
            id=1,
            entity_id=1,
            relative_path="main.py",
            is_code=True,
            is_context=False,
            language="python",
        )
    ]

    prev_analysis = AnalysisRecord(
        id=10,
        entity_id=1,
        name="Update Proj",
        type="utility",
        description="Utilitario de testes",
        purpose="Facilitar testes",
        languages_json='["Python"]',
        technologies_json='["pytest"]',
        confidence=0.9,
        entity_fingerprint="fp_antigo",
    )

    delta = FileDelta(
        added=[
            HashedFile(
                path=proj_dir / "extra.py",
                relative_path="extra.py",
                file_hash="h_extra",
                extension=".py",
                file_type="code",
                is_code=True,
                is_context=False,
                size_bytes=10,
                mtime=1.0,
            )
        ],
        modified=[],
        deleted=[],
        unchanged=[],
    )

    ctx = build_context(
        entity=entity,
        files=files,
        previous_analysis=prev_analysis,
        changes=delta,
    )

    assert ctx.operation == "update"
    assert ctx.previous_analysis is not None
    assert ctx.previous_analysis["name"] == "Update Proj"
    assert ctx.previous_analysis["languages"] == ["Python"]

    assert ctx.changes is not None
    assert ctx.changes["added"] == ["extra.py"]
    assert ctx.changes["summary"]["added"] == 1


def test_build_context_missing_file_on_disk(tmp_path):
    """Garante que arquivos listados no banco mas ausentes no disco são tratados graciosamente."""
    proj_dir = tmp_path / "empty_dir"
    proj_dir.mkdir()

    entity = EntityRecord(
        id=1,
        path=str(proj_dir.resolve()),
        name="empty_dir",
        type="project",
    )

    # Arquivo não existe no disco
    files = [
        FileRecord(
            id=1,
            entity_id=1,
            relative_path="phantom.py",
            is_code=True,
            is_context=False,
            language="python",
        )
    ]

    ctx = build_context(entity=entity, files=files)
    assert ctx.operation == "initial"
    assert "phantom.py" in ctx.file_structure
    assert ctx.file_structure["phantom.py"]["lines_count"] == 0


def test_llm_context_to_dict():
    """Valida serialização para dicionário."""
    ctx = LLMContext(
        operation="initial",
        entity_info={"name": "test"},
        file_structure={"main.py": {"lines_count": 5}},
        context_files_content={"README.md": "docs"},
    )
    d = ctx.to_dict()
    assert d["operation"] == "initial"
    assert d["entity"]["name"] == "test"
    assert d["file_structure"]["main.py"]["lines_count"] == 5
    assert d["context_files"]["README.md"] == "docs"
