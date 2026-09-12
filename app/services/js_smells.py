from pathlib import Path

from .js_analyzer import _get_language


def detect_javascript_code_smells(file_path: Path) -> list:
    """
    Detect common code smells in JavaScript,
    JSX, TypeScript, and TSX files.
    """

    findings = []

    language = _get_language(file_path)

    if language is None:
        return [
            {
                "file": str(file_path),
                "type": "unsupported_file",
                "message": "Unsupported JavaScript/TypeScript file.",
                "severity": "low",
            }
        ]

    try:
        source = file_path.read_bytes()

        from tree_sitter import Parser

        parser = Parser()
        parser.language = language

        tree = parser.parse(source)
        root = tree.root_node

    except (OSError, UnicodeDecodeError) as error:
        return [
            {
                "file": str(file_path),
                "type": "parse_error",
                "message": str(error),
                "severity": "high",
            }
        ]

    # --------------------------------------------------
    # 1. LARGE FILE
    # --------------------------------------------------

    total_lines = len(source.decode("utf-8", errors="ignore").splitlines())

    if total_lines > 300:
        findings.append({
            "file": str(file_path),
            "type": "large_file",
            "message": f"File contains {total_lines} lines.",
            "severity": "medium",
        })

    # --------------------------------------------------
    # WALK TREE
    # --------------------------------------------------

    complexity = 1

    function_nodes = {
        "function_declaration",
        "function_expression",
        "arrow_function",
        "method_definition",
    }

    loop_nodes = {
        "for_statement",
        "for_in_statement",
        "for_of_statement",
        "while_statement",
        "do_statement",
    }

    def walk(node):

        nonlocal complexity

        # ----------------------------------------------
        # COMPLEXITY
        # ----------------------------------------------

        if node.type == "if_statement":
            complexity += 1

        elif node.type in loop_nodes:
            complexity += 1

        elif node.type == "ternary_expression":
            complexity += 1

        elif node.type == "catch_clause":
            complexity += 1

        elif node.type == "binary_expression":

            for child in node.children:

                if child.type in {"&&", "||"}:
                    complexity += 1
                    break

        # ----------------------------------------------
        # FUNCTION SMELLS
        # ----------------------------------------------

        if node.type in function_nodes:

            # ------------------------------------------
            # LONG FUNCTION
            # ------------------------------------------

            if node.start_point and node.end_point:

                function_lines = (
                    node.end_point[0]
                    - node.start_point[0]
                    + 1
                )

                if function_lines > 50:

                    findings.append({
                        "file": str(file_path),
                        "type": "long_function",
                        "message": (
                            f"Function contains "
                            f"{function_lines} lines."
                        ),
                        "severity": "medium",
                    })

            # ------------------------------------------
            # TOO MANY PARAMETERS
            # ------------------------------------------

            parameter_count = 0

            for child in node.children:

                if child.type in {
                    "formal_parameters",
                    "required_parameters",
                    "optional_parameters",
                }:

                    parameter_count = sum(
                        1
                        for parameter in child.named_children
                        if parameter.type not in {
                            ",",
                        }
                    )

                    break

            if parameter_count > 5:

                findings.append({
                    "file": str(file_path),
                    "type": "too_many_parameters",
                    "message": (
                        f"Function has "
                        f"{parameter_count} parameters."
                    ),
                    "severity": "medium",
                })

        for child in node.children:
            walk(child)

    walk(root)

    # --------------------------------------------------
    # 2. HIGH COMPLEXITY
    # --------------------------------------------------

    if complexity > 10:
        findings.append({
            "file": str(file_path),
            "type": "high_complexity",
            "message": (
                f"Cyclomatic complexity is {complexity}."
            ),
            "severity": "high",
        })

    return findings