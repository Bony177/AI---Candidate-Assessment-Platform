import ast
from pathlib import Path

from .metrics import calculate_complexity


def analyze_python_file(file_path: Path) -> dict:
    """
    Analyze a single Python file using Python's AST.
    """

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

    except (SyntaxError, UnicodeDecodeError) as e:
        return {
            "file": str(file_path),
            "success": False,
            "error": str(e),
        }

    functions = 0
    classes = 0
    if_statements = 0
    loops = 0
    imports = 0

    for node in ast.walk(tree):

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions += 1

        elif isinstance(node, ast.ClassDef):
            classes += 1

        elif isinstance(node, ast.If):
            if_statements += 1

        elif isinstance(node, (ast.For, ast.While)):
            loops += 1

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports += 1

    complexity = calculate_complexity(tree)

    return {
        "file": str(file_path),
        "success": True,
        "functions": functions,
        "classes": classes,
        "if_statements": if_statements,
        "loops": loops,
        "imports": imports,
        "complexity": complexity,
    }