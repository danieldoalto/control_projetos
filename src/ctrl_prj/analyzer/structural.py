"""Analisador estrutural leve de código-fonte para Python, Rust, JS/TS e Bash."""

import ast
from pathlib import Path
import re
from typing import List, Optional, Set, Union
import warnings

from ctrl_prj.analyzer.models import FileStructure

# ----------------------------------------------------------------------
# Regex Patterns
# ----------------------------------------------------------------------

# Rust
RE_RUST_USE = re.compile(r"^\s*(?:pub\s+)?use\s+([^;]+);", re.MULTILINE)
RE_RUST_MOD = re.compile(r"^\s*(?:pub\s+)?mod\s+([a-zA-Z0-9_]+);", re.MULTILINE)
RE_RUST_STRUCT = re.compile(r"^\s*(?:pub(?:\([^\)]+\))?\s+)?struct\s+([a-zA-Z0-9_]+)", re.MULTILINE)
RE_RUST_ENUM = re.compile(r"^\s*(?:pub(?:\([^\)]+\))?\s+)?enum\s+([a-zA-Z0-9_]+)", re.MULTILINE)
RE_RUST_TRAIT = re.compile(r"^\s*(?:pub(?:\([^\)]+\))?\s+)?trait\s+([a-zA-Z0-9_]+)", re.MULTILINE)
RE_RUST_FN = re.compile(
    r"^\s*(?:pub(?:\([^\)]+\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+([a-zA-Z0-9_]+)\s*[\(<]",
    re.MULTILINE,
)
RE_RUST_IMPL = re.compile(r"^\s*impl(?:\s*<[^>]+>)?\s+([a-zA-Z0-9_:]+)", re.MULTILINE)

# JavaScript / TypeScript
RE_JS_IMPORT = re.compile(
    r"^\s*import\s+(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
RE_JS_REQUIRE = re.compile(r"(?:const|let|var)\s+[\w${},\s]+\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\)")
RE_JS_CLASS = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?class\s+([a-zA-Z0-9_$]+)", re.MULTILINE)
RE_JS_FUNCTION = re.compile(
    r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*([a-zA-Z0-9_$]+)?\s*\(",
    re.MULTILINE,
)
RE_JS_ARROW_FN = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>",
    re.MULTILINE,
)
RE_JS_EXPORT_NAMED = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:const|let|var|function|class|type|interface|enum)\s+([a-zA-Z0-9_$]+)",
    re.MULTILINE,
)
RE_JS_EXPORT_DEFAULT = re.compile(
    r"^\s*export\s+default\s+([a-zA-Z0-9_$]+);?",
    re.MULTILINE,
)
RE_JS_MODULE_EXPORTS = re.compile(
    r"exports\.([a-zA-Z0-9_$]+)\s*=",
    re.MULTILINE,
)

# Bash
RE_BASH_SHEBANG = re.compile(r"^#!\s*(/\S+)")
RE_BASH_SOURCE = re.compile(r"^\s*(?:source|\.)\s+(\S+)", re.MULTILINE)
RE_BASH_FUNCTION = re.compile(
    r"^\s*(?:function\s+([a-zA-Z0-9_-]+)(?:\s*\(\s*\))?|([a-zA-Z0-9_-]+)\s*\(\s*\))\s*\{",
    re.MULTILINE,
)


# ----------------------------------------------------------------------
# Parsers específicos por linguagem
# ----------------------------------------------------------------------

def _analyze_python(code: str, line_count: int) -> FileStructure:
    """Extrai estrutura de código Python usando o módulo AST com fallback seguro."""
    imports: List[str] = []
    classes: List[str] = []
    functions: List[str] = []

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join(alias.name for alias in node.names)
                imports.append(f"{module}.{names}" if module else names)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
    except SyntaxError:
        # Fallback leve via regex caso o código tenha erros de sintaxe ou versão incompatível
        for match in re.finditer(r"^\s*(?:from\s+(\S+)\s+import|import\s+([^#\n]+))", code, re.MULTILINE):
            imports.append(match.group(1) or match.group(2).strip())
        for match in re.finditer(r"^\s*class\s+([a-zA-Z0-9_]+)", code, re.MULTILINE):
            classes.append(match.group(1))
        for match in re.finditer(r"^\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)", code, re.MULTILINE):
            functions.append(match.group(1))

    return FileStructure(
        lines_count=line_count,
        imports=sorted(list(set(imports))),
        classes=sorted(list(set(classes))),
        functions=sorted(list(set(functions))),
        exports=[],
    )


def _analyze_rust(code: str, line_count: int) -> FileStructure:
    """Extrai estrutura de código Rust usando expressões regulares."""
    imports: Set[str] = set()
    classes: Set[str] = set()  # Structs, Enums, Traits
    functions: Set[str] = set()
    exports: Set[str] = set()

    for match in RE_RUST_USE.finditer(code):
        imports.add(match.group(1).strip())
    for match in RE_RUST_MOD.finditer(code):
        imports.add(f"mod {match.group(1).strip()}")

    for match in RE_RUST_STRUCT.finditer(code):
        classes.add(f"struct {match.group(1)}")
    for match in RE_RUST_ENUM.finditer(code):
        classes.add(f"enum {match.group(1)}")
    for match in RE_RUST_TRAIT.finditer(code):
        classes.add(f"trait {match.group(1)}")

    for match in RE_RUST_FN.finditer(code):
        functions.add(match.group(1))

    for match in RE_RUST_IMPL.finditer(code):
        exports.add(f"impl {match.group(1)}")

    return FileStructure(
        lines_count=line_count,
        imports=sorted(list(imports)),
        classes=sorted(list(classes)),
        functions=sorted(list(functions)),
        exports=sorted(list(exports)),
    )


def _analyze_javascript_typescript(code: str, line_count: int) -> FileStructure:
    """Extrai estrutura de código JavaScript e TypeScript usando expressões regulares."""
    imports: Set[str] = set()
    classes: Set[str] = set()
    functions: Set[str] = set()
    exports: Set[str] = set()

    for match in RE_JS_IMPORT.finditer(code):
        imports.add(match.group(1))
    for match in RE_JS_REQUIRE.finditer(code):
        imports.add(match.group(1))

    for match in RE_JS_CLASS.finditer(code):
        classes.add(match.group(1))

    for match in RE_JS_FUNCTION.finditer(code):
        fn_name = match.group(1)
        if fn_name:
            functions.add(fn_name)

    for match in RE_JS_ARROW_FN.finditer(code):
        functions.add(match.group(1))

    for match in RE_JS_EXPORT_NAMED.finditer(code):
        exports.add(match.group(1))

    for match in RE_JS_EXPORT_DEFAULT.finditer(code):
        name = match.group(1)
        if name not in {"class", "function", "const", "let", "var"}:
            exports.add(name)

    for match in RE_JS_MODULE_EXPORTS.finditer(code):
        exports.add(match.group(1))

    return FileStructure(
        lines_count=line_count,
        imports=sorted(list(imports)),
        classes=sorted(list(classes)),
        functions=sorted(list(functions)),
        exports=sorted(list(exports)),
    )


def _analyze_bash(code: str, line_count: int) -> FileStructure:
    """Extrai estrutura de scripts Bash/Shell usando expressões regulares."""
    imports: Set[str] = set()
    functions: Set[str] = set()
    exports: Set[str] = set()

    # Shebang
    first_line = code.split("\n", 1)[0] if code else ""
    shebang_match = RE_BASH_SHEBANG.match(first_line)
    if shebang_match:
        exports.add(f"shebang:{shebang_match.group(1)}")

    for match in RE_BASH_SOURCE.finditer(code):
        imports.add(match.group(1))

    for match in RE_BASH_FUNCTION.finditer(code):
        fn_name = match.group(1) or match.group(2)
        if fn_name:
            functions.add(fn_name)

    return FileStructure(
        lines_count=line_count,
        imports=sorted(list(imports)),
        classes=[],
        functions=sorted(list(functions)),
        exports=sorted(list(exports)),
    )


# ----------------------------------------------------------------------
# Função Principal
# ----------------------------------------------------------------------

def _infer_language(file_path: Path, language: Optional[str] = None) -> str:
    """Normaliza ou infere o identificador da linguagem a partir da extensão ou nome."""
    if language:
        return language.lower().strip()

    name_lower = file_path.name.lower()
    suffix = file_path.suffix.lower()

    if suffix == ".py":
        return "python"
    if suffix == ".rs":
        return "rust"
    if suffix in {".js", ".mjs", ".cjs", ".jsx"}:
        return "javascript"
    if suffix in {".ts", ".tsx"}:
        return "typescript"
    if suffix in {".sh", ".bash"} or name_lower.startswith(".bash"):
        return "bash"

    return suffix.lstrip(".")


def analyze_file(
    file_path: Union[str, Path],
    language: Optional[str] = None,
) -> FileStructure:
    """Analisa o conteúdo estrutural de um arquivo de código.

    Args:
        file_path: Caminho do arquivo a ser analisado.
        language: Nome ou identificador opcional da linguagem.

    Returns:
        FileStructure contendo a contagem de linhas e listas de imports, classes, funções e exports.
    """
    path_obj = Path(file_path)
    if not path_obj.is_file():
        return FileStructure(lines_count=0)

    try:
        content = path_obj.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return FileStructure(lines_count=0)

    lines = content.splitlines()
    line_count = len(lines)

    lang = _infer_language(path_obj, language)

    if lang == "python":
        return _analyze_python(content, line_count)
    elif lang == "rust":
        return _analyze_rust(content, line_count)
    elif lang in {"javascript", "typescript", "typescriptreact"}:
        return _analyze_javascript_typescript(content, line_count)
    elif lang in {"bash", "sh"}:
        return _analyze_bash(content, line_count)

    # Formatos de contexto ou não suportados pelo analisador estrutural de código
    return FileStructure(lines_count=line_count)
