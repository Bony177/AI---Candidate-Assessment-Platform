import ast
from pathlib import Path

from .metrics import calculate_complexity


def detect_code_smells(file_path: Path) -> list:
    """
    Detect common code smells in a Python file.
    """

    findings = []

    try:
        source = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        tree = ast.parse(source)

    except (SyntaxError, UnicodeDecodeError) as e:
        return [
            {
                "file": str(file_path),
                "type": "parse_error",
                "message": str(e),
            }
        ]

    # --------------------------------------------------
    # 1. LARGE FILE
    # --------------------------------------------------

    total_lines = len(source.splitlines())

    if total_lines > 300:
        findings.append({
            "file": str(file_path),
            "type": "large_file",
            "message": f"File contains {total_lines} lines.",
            "severity": "medium",
        })

    # --------------------------------------------------
    # 2. HIGH COMPLEXITY
    # --------------------------------------------------

    complexity = calculate_complexity(tree)

    if complexity > 10:
        findings.append({
            "file": str(file_path),
            "type": "high_complexity",
            "message": f"Cyclomatic complexity is {complexity}.",
            "severity": "high",
        })

    # --------------------------------------------------
    # 3. FUNCTION-LEVEL SMELLS
    # --------------------------------------------------

    for node in ast.walk(tree):

        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):

            # ------------------------------------------
            # LONG FUNCTION
            # ------------------------------------------

            if hasattr(node, "end_lineno"):

                function_lines = (
                    node.end_lineno - node.lineno + 1
                )

                if function_lines > 50:

                    findings.append({
                        "file": str(file_path),
                        "type": "long_function",
                        "function": node.name,
                        "message": (
                            f"Function '{node.name}' "
                            f"contains {function_lines} lines."
                        ),
                        "severity": "medium",
                    })

            # ------------------------------------------
            # TOO MANY PARAMETERS
            # ------------------------------------------

            parameter_count = len(node.args.args)

            if parameter_count > 5:

                findings.append({
                    "file": str(file_path),
                    "type": "too_many_parameters",
                    "function": node.name,
                    "message": (
                        f"Function '{node.name}' "
                        f"has {parameter_count} parameters."
                    ),
                    "severity": "medium",
                })

    return findings