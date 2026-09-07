from pathlib import Path


def calculate_loc(file_path: Path) -> dict:
    """
    Calculate basic lines-of-code metrics.
    """

    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "total_lines": 0,
            "code_lines": 0,
            "comment_lines": 0,
            "blank_lines": 0,
        }

    lines = source.splitlines()

    total_lines = len(lines)
    blank_lines = 0
    comment_lines = 0
    code_lines = 0

    for line in lines:

        stripped = line.strip()

        if not stripped:
            blank_lines += 1

        elif stripped.startswith("#"):
            comment_lines += 1

        else:
            code_lines += 1

    return {
        "total_lines": total_lines,
        "code_lines": code_lines,
        "comment_lines": comment_lines,
        "blank_lines": blank_lines,
    }

import ast
from pathlib import Path


def calculate_complexity(tree: ast.AST) -> int:

    complexity = 1

    for node in ast.walk(tree):

        if isinstance(
            node,
            (
                ast.If,
                ast.For,
                ast.While,
                ast.IfExp,
            ),
        ):
            complexity += 1

        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1

        elif isinstance(node, ast.ExceptHandler):
            complexity += 1

    return complexity