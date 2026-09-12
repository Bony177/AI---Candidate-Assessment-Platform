from pathlib import Path

from .ast_analyzer import analyze_python_file
from .js_analyzer import analyze_javascript_file
from .metrics import calculate_loc
from .security import scan_file_for_secrets
from .test_detector import detect_tests
from .smells import detect_code_smells
from .scoring import calculate_static_score
from .js_smells import detect_javascript_code_smells


SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}

IGNORED_DIRECTORIES = {
    ".git",
    "venv",
    ".venv",
    "node_modules",
    "__pycache__",
}


def analyze_repository(repo_path: str) -> dict:
    """
    Run complete static analysis on a repository.

    Supports:
    - Python
    - JavaScript
    - JSX
    - TypeScript
    - TSX

    Includes:
    - AST analysis
    - LOC metrics
    - Secret detection
    - Test detection
    - Code smell detection
    - Static analysis scoring
    """

    repo = Path(repo_path)

    # --------------------------------------------------
    # FIND SUPPORTED SOURCE FILES
    # --------------------------------------------------

    source_files = []

    for path in repo.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        if any(
            ignored in path.parts
            for ignored in IGNORED_DIRECTORIES
        ):
            continue

        # Keep test files out of production source analysis.
        path_parts = {part.lower() for part in path.parts}

        if (
            "test" in path_parts
            or "tests" in path_parts
            or path.name.lower().startswith("test_")
            or path.name.lower().endswith("_test.py")
            or path.name.lower().endswith(".test.js")
            or path.name.lower().endswith(".test.jsx")
            or path.name.lower().endswith(".test.ts")
            or path.name.lower().endswith(".test.tsx")
            or path.name.lower().endswith(".spec.js")
            or path.name.lower().endswith(".spec.jsx")
            or path.name.lower().endswith(".spec.ts")
            or path.name.lower().endswith(".spec.tsx")
        ):
            continue

        source_files.append(path)

    # --------------------------------------------------
    # INITIALIZE RESULTS
    # --------------------------------------------------

    file_results = []

    secret_findings = []

    total_code_lines = 0
    total_functions = 0
    total_classes = 0
    total_complexity = 0
    total_smells = 0

    # --------------------------------------------------
    # ANALYZE EACH SOURCE FILE
    # --------------------------------------------------

    for file_path in source_files:

        suffix = file_path.suffix.lower()

        # ----------------------------------------------
        # LANGUAGE-SPECIFIC AST ANALYSIS
        # ----------------------------------------------

        if suffix == ".py":
            ast_result = analyze_python_file(file_path)
        else:
            ast_result = analyze_javascript_file(file_path)

        # ----------------------------------------------
        # LOC ANALYSIS
        # ----------------------------------------------

        loc_result = calculate_loc(file_path)

        # ----------------------------------------------
        # SECRET SCAN
        # ----------------------------------------------

        secrets = scan_file_for_secrets(file_path)

        secret_findings.extend(secrets)

        # ----------------------------------------------
        # CODE SMELLS
        # ----------------------------------------------

        # The existing smell detector is Python-oriented.
        # Keep it on Python files for now so we don't
        # break the existing analyzer.
        if suffix == ".py":
            smells = detect_code_smells(file_path)
        else:
            smells = detect_javascript_code_smells(file_path)

        # ----------------------------------------------
        # HANDLE AST FAILURE
        # ----------------------------------------------

        if not ast_result["success"]:

            file_results.append({
                "file": str(file_path),
                "language": suffix.lstrip("."),
                "ast": ast_result,
                "loc": loc_result,
                "secrets": secrets,
                "smells": smells,
            })

            continue

        # ----------------------------------------------
        # AGGREGATE METRICS
        # ----------------------------------------------

        total_code_lines += loc_result["code_lines"]

        total_functions += ast_result["functions"]

        total_classes += ast_result["classes"]

        total_complexity += ast_result["complexity"]

        total_smells += len(smells)

        # ----------------------------------------------
        # STORE FILE RESULT
        # ----------------------------------------------

        file_results.append({
            "file": str(file_path),
            "language": suffix.lstrip("."),
            "ast": ast_result,
            "loc": loc_result,
            "secrets": secrets,
            "smells": smells,
        })

    # --------------------------------------------------
    # TEST DETECTION
    # --------------------------------------------------

    test_result = detect_tests(repo)

    # --------------------------------------------------
    # CALCULATE AVERAGE COMPLEXITY
    # --------------------------------------------------

    average_complexity = (
        total_complexity / len(source_files)
        if source_files
        else 0
    )

    # --------------------------------------------------
    # CALCULATE STATIC ANALYSIS SCORE
    # --------------------------------------------------

    static_score = calculate_static_score(
        complexity=average_complexity,
        total_code_lines=total_code_lines,
        files_analyzed=len(source_files),
        has_tests=test_result["has_tests"],
        secret_count=len(secret_findings),
        smell_count=total_smells,
    )

    # --------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------

    return {
        "repository": str(repo),

        "files_analyzed": len(source_files),

        "total_code_lines": total_code_lines,

        "total_functions": total_functions,

        "total_classes": total_classes,

        "total_complexity": total_complexity,

        "average_complexity": average_complexity,

        "total_smells": total_smells,

        "potential_secrets": secret_findings,

        "tests": test_result,

        "static_score": static_score,

        "files": file_results,
    }