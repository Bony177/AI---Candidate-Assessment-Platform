from pathlib import Path
import ast


PYTHON_EXTENSIONS = {
    ".py",
}

JAVASCRIPT_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}


def calculate_loc(file_path: Path) -> dict:
    """
    Calculate basic lines-of-code metrics.

    Supports:
    - Python comments: #
    - JavaScript/TypeScript comments: //
    - JavaScript/TypeScript block comments: /* */
    """

    try:
        source = file_path.read_text(encoding="utf-8")

    except (OSError, UnicodeDecodeError):
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

    suffix = file_path.suffix.lower()

    # --------------------------------------------------
    # PYTHON
    # --------------------------------------------------

    if suffix in PYTHON_EXTENSIONS:

        for line in lines:

            stripped = line.strip()

            if not stripped:
                blank_lines += 1

            elif stripped.startswith("#"):
                comment_lines += 1

            else:
                code_lines += 1

    # --------------------------------------------------
    # JAVASCRIPT / TYPESCRIPT
    # --------------------------------------------------

    elif suffix in JAVASCRIPT_EXTENSIONS:

        inside_block_comment = False

        for line in lines:

            stripped = line.strip()

            # Blank line
            if not stripped:
                blank_lines += 1
                continue

            # Currently inside /* ... */ comment
            if inside_block_comment:

                comment_lines += 1

                if "*/" in stripped:
                    inside_block_comment = False

                continue

            # Single-line comment
            if stripped.startswith("//"):
                comment_lines += 1
                continue

            # Block comment starts and ends on same line
            if stripped.startswith("/*"):

                comment_lines += 1

                if "*/" not in stripped[2:]:
                    inside_block_comment = True

                continue

            # Normal code
            code_lines += 1

    # --------------------------------------------------
    # UNSUPPORTED FILE TYPE
    # --------------------------------------------------

    else:

        for line in lines:

            stripped = line.strip()

            if not stripped:
                blank_lines += 1
            else:
                code_lines += 1

    return {
        "total_lines": total_lines,
        "code_lines": code_lines,
        "comment_lines": comment_lines,
        "blank_lines": blank_lines,
    }


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