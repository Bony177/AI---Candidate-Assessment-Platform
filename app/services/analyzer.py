from pathlib import Path
import logging

from .ast_analyzer import analyze_python_file
from .js_analyzer import analyze_javascript_file
from .metrics import calculate_loc
from .gitleaks import scan_repository_with_gitleaks
from .test_detector import detect_tests
from .smells import detect_code_smells
from .scoring import calculate_static_score
from .js_smells import detect_javascript_code_smells

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}

LANGUAGE_NAMES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JSX",
    ".ts": "TypeScript",
    ".tsx": "TSX",
}


IGNORED_DIRECTORIES = {
    ".git",
    "venv",
    ".venv",
    "node_modules",
    "__pycache__",
}


def _build_analysis_coverage(file_details: list[dict]) -> dict:
    """Aggregate unique discovered file outcomes into a coverage summary."""
    priority = {"analyzed": 0, "skipped": 1, "failed": 2}
    unique_details = {}
    for detail in file_details:
        path = detail.get("path")
        if not path:
            continue
        current = unique_details.get(path)
        if current is None or priority.get(
            detail.get("status"), -1
        ) > priority.get(current.get("status"), -1):
            unique_details[path] = detail

    details = list(unique_details.values())
    counts = {
        outcome: sum(detail.get("status") == outcome for detail in details)
        for outcome in ("analyzed", "skipped", "failed")
    }
    discovered = len(details)

    if discovered == 0:
        status = "no_supported_files"
        percentage = None
    elif counts["analyzed"] == discovered:
        status = "complete"
        percentage = 100.0
    else:
        status = "partial"
        percentage = round(counts["analyzed"] / discovered * 100, 1)

    return {
        "supported_files_discovered": discovered,
        "files_analyzed": counts["analyzed"],
        "files_skipped": counts["skipped"],
        "files_failed": counts["failed"],
        "coverage_percentage": percentage,
        "status": status,
        "file_details": details,
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
    - Gitleaks security scanning
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
    file_details = []

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
        relative_path = file_path.relative_to(repo).as_posix()
        stage = "python_ast" if suffix == ".py" else "tree_sitter"
        ast_result = None
        loc_result = {}
        smells = []
        failure_reason = None

        try:
            if suffix == ".py":
                ast_result = analyze_python_file(file_path)
            else:
                ast_result = analyze_javascript_file(file_path)

            if not ast_result.get("success"):
                failure_reason = (
                    "Python parsing failed."
                    if suffix == ".py"
                    else "JavaScript/TypeScript parsing failed."
                )
            else:
                stage = "lines_of_code"
                loc_result = calculate_loc(file_path)
                if loc_result.get("success") is False:
                    error_code = loc_result.get("error_code", "read_error")
                    failure_reason = (
                        f"Lines-of-code analysis failed ({error_code})."
                    )

            if failure_reason is None:
                stage = "code_smells"
                if suffix == ".py":
                    smells = detect_code_smells(file_path)
                else:
                    smells = detect_javascript_code_smells(file_path)
                if any(
                    smell.get("type") in {"parse_error", "unsupported_file"}
                    for smell in smells
                ):
                    failure_reason = (
                        "Code-smell analysis could not process the file."
                    )
                    smells = []
        except Exception as error:
            error_code = type(error).__name__
            failure_reason = f"Analysis failed during {stage} ({error_code})."
            logger.warning(
                "File analysis failed for %s during %s (%s)",
                relative_path,
                stage,
                error_code,
            )

        if ast_result is not None:
            ast_result["file"] = relative_path
        for smell in smells:
            if smell.get("file"):
                smell["file"] = relative_path

        outcome = "failed" if failure_reason else "analyzed"
        file_detail = {
            "path": relative_path,
            "language": LANGUAGE_NAMES[suffix],
            "status": outcome,
            "stage": stage if failure_reason else "static_analysis",
        }
        if failure_reason:
            file_detail["reason"] = failure_reason
        file_details.append(file_detail)

        file_results.append({
            "file": relative_path,
            "language": suffix.lstrip("."),
            "ast": ast_result,
            "loc": loc_result,
            "secrets": [],
            "smells": smells,
        })

        if failure_reason:
            continue

        # ----------------------------------------------
        # AGGREGATE METRICS
        # ----------------------------------------------

        total_code_lines += loc_result["code_lines"]

        total_functions += ast_result["functions"]

        total_classes += ast_result["classes"]

        total_complexity += ast_result["complexity"]

        total_smells += len(smells)

    # --------------------------------------------------
    # GITLEAKS SECURITY SCAN
    # --------------------------------------------------

    security_scan = scan_repository_with_gitleaks(repo)
    findings_by_file = {}
    for finding in security_scan["findings"]:
        file_path = finding.get("file")
        if file_path:
            findings_by_file.setdefault(file_path, []).append(finding)

    for file_result in file_results:
        relative_file = Path(file_result["file"]).as_posix()
        file_result["secrets"] = findings_by_file.get(relative_file, [])

    # --------------------------------------------------
    # TEST DETECTION
    # --------------------------------------------------

    test_result = detect_tests(repo)
    test_result["test_files"] = [
        Path(path).relative_to(repo).as_posix()
        for path in test_result["test_files"]
    ]

    # --------------------------------------------------
    # CALCULATE AVERAGE COMPLEXITY
    # --------------------------------------------------

    files_analyzed = sum(
        detail["status"] == "analyzed"
        for detail in file_details
    )
    analysis_coverage = _build_analysis_coverage(file_details)

    average_complexity = (
        total_complexity / files_analyzed
        if files_analyzed
        else 0
    )

    # --------------------------------------------------
    # WARNING DENSITY PER 1,000 LOC
    # --------------------------------------------------
    # Formula: (total_smells / total_code_lines) * 1000
    #
    # raw_warning_count = total_smells (code smell findings,
    #   deduplicated per-file across Python and JS/TS).
    # LOC denominator   = total_code_lines (blank and comment
    #   lines excluded by calculate_loc).
    #
    # Zero LOC: density is 0 with loc_status "zero_loc"
    # so the value is not misinterpreted as excellent quality.
    # --------------------------------------------------

    if total_code_lines > 0:
        warning_density_per_1000_loc = round(
            (total_smells / total_code_lines) * 1000, 2
        )
        loc_status = "ok"
    else:
        warning_density_per_1000_loc = 0
        loc_status = (
            "zero_loc — no code lines found; "
            "density is 0 by convention, not indicative "
            "of code quality"
        )

    # --------------------------------------------------
    # CALCULATE STATIC ANALYSIS SCORE
    # --------------------------------------------------

    static_score = calculate_static_score(
        complexity=average_complexity,
        total_code_lines=total_code_lines,
        files_analyzed=files_analyzed,
        has_tests=test_result["has_tests"],
        security_findings=security_scan["findings"],
        security_scan_status=security_scan["status"],
        warning_density_per_1000_loc=warning_density_per_1000_loc,
    )

    # --------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------

    return {
        "repository": repo.name,

        "files_analyzed": files_analyzed,

        "analysis_coverage": analysis_coverage,

        "total_code_lines": total_code_lines,

        "total_functions": total_functions,

        "total_classes": total_classes,

        "total_complexity": total_complexity,

        "average_complexity": average_complexity,

        "total_smells": total_smells,

        "warning_density_per_1000_loc": warning_density_per_1000_loc,

        "loc_status": loc_status,

        "potential_secrets": security_scan["findings"],

        "security_scan": security_scan,

        "tests": test_result,

        "static_score": static_score,

        "files": file_results,
    }