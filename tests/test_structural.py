"""Testes automatizados para a análise estrutural local (Structural Analyzer)."""

from pathlib import Path
import pytest

from ctrl_prj.analyzer import FileStructure, analyze_file


def test_analyze_python_file(tmp_path):
    """Testa extração de estrutura em arquivo Python."""
    code = """import os
import sys
from pathlib import Path, PurePath

class DatabaseService:
    def __init__(self):
        pass

    async def connect(self):
        pass

def calculate_sum(a: int, b: int) -> int:
    return a + b
"""
    py_file = tmp_path / "service.py"
    py_file.write_text(code, encoding="utf-8")

    res: FileStructure = analyze_file(py_file)

    assert res.lines_count == len(code.splitlines())
    assert "os" in res.imports
    assert "sys" in res.imports
    assert "pathlib.Path, PurePath" in res.imports
    assert "DatabaseService" in res.classes
    assert "connect" in res.functions
    assert "calculate_sum" in res.functions
    assert "__init__" in res.functions


def test_analyze_python_syntax_error_fallback(tmp_path):
    """Testa fallback gracioso de Python quando há erro de sintaxe."""
    bad_code = """import math
def broken_fn(
    print("invalid python code")
class SimpleClass:
    pass
"""
    bad_py = tmp_path / "broken.py"
    bad_py.write_text(bad_code, encoding="utf-8")

    res = analyze_file(bad_py)
    assert res.lines_count == len(bad_code.splitlines())
    assert "math" in res.imports
    assert "SimpleClass" in res.classes


def test_analyze_rust_file(tmp_path):
    """Testa extração de estrutura em arquivo Rust."""
    code = """use std::collections::HashMap;
pub use crate::models::User;
mod database;

pub struct ServerConfig {
    pub port: u16,
}

enum AppState {
    Starting,
    Running,
}

pub trait Service {
    fn name(&self) -> &str;
}

pub async fn start_server() -> Result<(), ()> {
    Ok(())
}

impl ServerConfig {
    pub fn new() -> Self {
        Self { port: 8080 }
    }
}
"""
    rs_file = tmp_path / "server.rs"
    rs_file.write_text(code, encoding="utf-8")

    res = analyze_file(rs_file)

    assert res.lines_count == len(code.splitlines())
    assert "std::collections::HashMap" in res.imports
    assert "crate::models::User" in res.imports
    assert "mod database" in res.imports
    assert "struct ServerConfig" in res.classes
    assert "enum AppState" in res.classes
    assert "trait Service" in res.classes
    assert "start_server" in res.functions
    assert "new" in res.functions
    assert "impl ServerConfig" in res.exports


def test_analyze_javascript_typescript_file(tmp_path):
    """Testa extração de estrutura em arquivo JS/TS."""
    code = """import React, { useState } from 'react';
const express = require('express');

export class UserController {
    constructor() {}
}

export async function authenticate(req, res) {
    return true;
}

const formatUserData = (user) => {
    return user.name;
};

const fetchData = async () => {
    return await api.get();
};

export default UserController;
"""
    ts_file = tmp_path / "controller.ts"
    ts_file.write_text(code, encoding="utf-8")

    res = analyze_file(ts_file)

    assert res.lines_count == len(code.splitlines())
    assert "react" in res.imports
    assert "express" in res.imports
    assert "UserController" in res.classes
    assert "authenticate" in res.functions
    assert "formatUserData" in res.functions
    assert "fetchData" in res.functions
    assert "UserController" in res.exports


def test_analyze_bash_file(tmp_path):
    """Testa extração de estrutura em script Bash."""
    code = """#!/bin/bash
source /etc/profile.d/app.sh
. ./helpers.sh

function deploy_app() {
    echo "Deploying..."
}

cleanup_tmp() {
    rm -rf /tmp/test
}
"""
    sh_file = tmp_path / "deploy.sh"
    sh_file.write_text(code, encoding="utf-8")

    res = analyze_file(sh_file)

    assert res.lines_count == len(code.splitlines())
    assert "/etc/profile.d/app.sh" in res.imports
    assert "./helpers.sh" in res.imports
    assert "deploy_app" in res.functions
    assert "cleanup_tmp" in res.functions
    assert "shebang:/bin/bash" in res.exports


def test_analyze_non_code_or_empty_file(tmp_path):
    """Testa arquivos sem suporte a código estrutural e arquivos vazios."""
    # Arquivo markdown
    md_file = tmp_path / "README.md"
    md_file.write_text("# Titulo\n\nDescricao curta.\n", encoding="utf-8")
    res_md = analyze_file(md_file)
    assert res_md.lines_count == 3
    assert res_md.imports == []
    assert res_md.classes == []
    assert res_md.functions == []

    # Arquivo vazio
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("", encoding="utf-8")
    res_empty = analyze_file(empty_file)
    assert res_empty.lines_count == 0
    assert res_empty.is_empty is True

    # Arquivo inexistente
    res_non_exist = analyze_file(tmp_path / "nao_existe.py")
    assert res_non_exist.lines_count == 0


def test_file_structure_to_dict():
    """Testa serialização para dicionário."""
    fs = FileStructure(
        lines_count=10,
        imports=["os"],
        classes=["App"],
        functions=["run"],
        exports=["App"],
    )
    d = fs.to_dict()
    assert d["lines_count"] == 10
    assert d["imports"] == ["os"]
    assert d["classes"] == ["App"]
    assert d["functions"] == ["run"]
    assert d["exports"] == ["App"]
