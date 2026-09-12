from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_javascript as javascript
import tree_sitter_typescript as typescript


def _get_language(file_path: Path):
    suffix = file_path.suffix.lower()

    if suffix == ".js":
        return Language(javascript.language())

    if suffix == ".jsx":
        return Language(javascript.language())

    if suffix == ".ts":
        return Language(typescript.language_typescript())

    if suffix == ".tsx":
        return Language(typescript.language_tsx())

    return None


def analyze_javascript_file(file_path: Path) -> dict:
    """
    Analyze a JavaScript, JSX, TypeScript, or TSX file.
    """

    language = _get_language(file_path)

    if language is None:
        return {
            "file": str(file_path),
            "success": False,
            "error": "Unsupported file type",
        }

    try:
        source = file_path.read_bytes()

        parser = Parser()
        parser.language = language

        tree = parser.parse(source)
        root = tree.root_node

    except (OSError, UnicodeDecodeError) as error:
        return {
            "file": str(file_path),
            "success": False,
            "error": str(error),
        }

    functions = 0
    classes = 0
    if_statements = 0
    loops = 0
    imports = 0
    exports = 0

    # Additional complexity constructs
    ternaries = 0
    boolean_operations = 0
    catch_blocks = 0

    function_nodes = {
        "function_declaration",
        "function_expression",
        "arrow_function",
        "method_definition",
    }

    class_nodes = {
        "class_declaration",
        "class",
    }

    loop_nodes = {
        "for_statement",
        "for_in_statement",
        "for_of_statement",
        "while_statement",
        "do_statement",
    }

    def walk(node):
        nonlocal functions
        nonlocal classes
        nonlocal if_statements
        nonlocal loops
        nonlocal imports
        nonlocal exports
        nonlocal ternaries
        nonlocal boolean_operations
        nonlocal catch_blocks

        if node.type in function_nodes:
            functions += 1

        elif node.type in class_nodes:
            classes += 1

        elif node.type == "if_statement":
            if_statements += 1

        elif node.type in loop_nodes:
            loops += 1

        elif node.type in {
            "import_statement",
            "import_clause",
        }:
            imports += 1

        elif node.type.startswith("export_"):
            exports += 1

        # JavaScript / TypeScript ternary operator:
        # condition ? value1 : value2
        elif node.type == "ternary_expression":
            ternaries += 1

        # JavaScript / TypeScript boolean operators:
        # && and ||
        elif node.type == "binary_expression":
            operator = None

            for child in node.children:
                if child.type in {"&&", "||"}:
                    operator = child.type
                    break

            if operator is not None:
                boolean_operations += 1

        # try { ... } catch (...) { ... }
        elif node.type == "catch_clause":
            catch_blocks += 1

        for child in node.children:
            walk(child)

    walk(root)

    # --------------------------------------------------
    # COMPLEXITY
    # --------------------------------------------------
    #
    # Same general philosophy as Python:
    #
    # Base complexity       = 1
    # if                    +1
    # loops                 +1
    # ternary               +1
    # && / ||               +1
    # catch                 +1
    #

    complexity = (
        1
        + if_statements
        + loops
        + ternaries
        + boolean_operations
        + catch_blocks
    )

    return {
        "file": str(file_path),
        "success": True,
        "language": file_path.suffix.lower().lstrip("."),
        "functions": functions,
        "classes": classes,
        "if_statements": if_statements,
        "loops": loops,
        "imports": imports,
        "exports": exports,
        "ternaries": ternaries,
        "boolean_operations": boolean_operations,
        "catch_blocks": catch_blocks,
        "complexity": complexity,
        "syntax_errors": root.has_error,
    }