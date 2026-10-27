def calculate_complexity_score(complexity: float) -> int:
    """
    Calculate score based on cyclomatic complexity.
    Maximum score: 25
    """

    if complexity <= 5:
        return 25

    elif complexity <= 10:
        return 20

    elif complexity <= 20:
        return 12

    elif complexity <= 30:
        return 5

    else:
        return 0


def calculate_structure_score(
    total_code_lines: int,
    files_analyzed: int
) -> int:
    """
    Calculate code structure score based on
    average lines of code per file.
    Maximum score: 20
    """

    if files_analyzed == 0:
        return 0

    average_lines = total_code_lines / files_analyzed

    if average_lines <= 100:
        return 20

    elif average_lines <= 200:
        return 15

    elif average_lines <= 300:
        return 10

    elif average_lines <= 500:
        return 5

    else:
        return 0


def calculate_testing_score(has_tests: bool) -> int:
    """
    Calculate testing score.
    Maximum score: 20
    """

    if has_tests:
        return 20

    return 0


SECURITY_FINDING_DEDUCTIONS = {
    "critical": 10,
    "high": 6,
    "medium": 3,
    "low": 1,
    "unclassified": 3,
}


def calculate_security_score(
    findings: list[dict],
    scan_status: str,
) -> int:
    """
    Score unique Gitleaks findings; incomplete scans fail closed.
    """

    if scan_status != "complete":
        return 0

    deduction = sum(
        SECURITY_FINDING_DEDUCTIONS.get(
            finding.get("severity", "unclassified"),
            SECURITY_FINDING_DEDUCTIONS["unclassified"],
        )
        for finding in findings
    )
    return max(0, 20 - deduction)


def calculate_code_smell_score(
    warning_density: float,
    total_code_lines: int,
) -> int:
    """
    Calculate the code smell score from warning density per 1,000 LOC.
    Maximum score: 15
    """

    if total_code_lines <= 0:
        return 0

    if warning_density <= 2:
        return 15

    elif warning_density <= 5:
        return 12

    elif warning_density <= 10:
        return 9

    elif warning_density <= 20:
        return 6

    elif warning_density <= 40:
        return 3

    else:
        return 0


def calculate_static_score(
    complexity: float,
    total_code_lines: int,
    files_analyzed: int,
    has_tests: bool,
    security_findings: list[dict],
    security_scan_status: str,
    warning_density_per_1000_loc: float,
) -> dict:
    """
    Calculate the complete static analysis score.
    """

    complexity_score = calculate_complexity_score(
        complexity
    )

    structure_score = calculate_structure_score(
        total_code_lines,
        files_analyzed
    )

    testing_score = calculate_testing_score(
        has_tests
    )

    security_score = calculate_security_score(
        security_findings,
        security_scan_status,
    )

    smell_score = calculate_code_smell_score(
        warning_density_per_1000_loc,
        total_code_lines,
    )

    total_score = (
        complexity_score
        + structure_score
        + testing_score
        + security_score
        + smell_score
    )

    return {
        "total_score": total_score,

        "breakdown": {
            "complexity": complexity_score,
            "structure": structure_score,
            "testing": testing_score,
            "security": security_score,
            "code_smells": smell_score,
        }
    }