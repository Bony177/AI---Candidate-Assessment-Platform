from pathlib import Path

from .ast_analyzer import analyze_python_file
from .metrics import calculate_loc
from .security import scan_file_for_secrets
from .test_detector import detect_tests
from .smells import detect_code_smells
from .scoring import calculate_static_score


def analyze_repository(repo_path: str) -> dict:
    """
    Run complete static analysis on a repository.

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
    # FIND PYTHON FILES
    # --------------------------------------------------

    python_files = []

    for path in repo.rglob("*.py"):

        if any(
            ignored in path.parts
            for ignored in [
                ".git",
                "venv",
                ".venv",
                "node_modules",
            ]
        ):
            continue

        python_files.append(path)

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
    # ANALYZE EACH PYTHON FILE
    # --------------------------------------------------

    for file_path in python_files:

        # -----------------------------
        # AST ANALYSIS
        # -----------------------------

        ast_result = analyze_python_file(file_path)

        if not ast_result["success"]:
            file_results.append(ast_result)
            continue

        # -----------------------------
        # LOC ANALYSIS
        # -----------------------------

        loc_result = calculate_loc(file_path)

        # -----------------------------
        # SECRET SCAN
        # -----------------------------

        secrets = scan_file_for_secrets(file_path)

        secret_findings.extend(secrets)

        # -----------------------------
        # CODE SMELL ANALYSIS
        # -----------------------------

        smells = detect_code_smells(file_path)

        # -----------------------------
        # AGGREGATE METRICS
        # -----------------------------

        total_code_lines += loc_result["code_lines"]

        total_functions += ast_result["functions"]

        total_classes += ast_result["classes"]

        total_complexity += ast_result["complexity"]

        total_smells += len(smells)

        # -----------------------------
        # STORE FILE RESULT
        # -----------------------------

        file_results.append({
            "file": str(file_path),
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
        total_complexity / len(python_files)
        if python_files
        else 0
    )

    # --------------------------------------------------
    # CALCULATE STATIC ANALYSIS SCORE
    # --------------------------------------------------

    static_score = calculate_static_score(
        complexity=average_complexity,
        total_code_lines=total_code_lines,
        files_analyzed=len(python_files),
        has_tests=test_result["has_tests"],
        secret_count=len(secret_findings),
        smell_count=total_smells,
    )

    # --------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------

    return {
        "repository": str(repo),

        "files_analyzed": len(python_files),

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