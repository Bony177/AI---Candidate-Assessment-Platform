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


def calculate_security_score(secret_count: int) -> int:
    """
    Calculate security score based on
    detected potential secrets.
    Maximum score: 20
    """

    if secret_count == 0:
        return 20

    elif secret_count == 1:
        return 10

    else:
        return 0


def calculate_smell_score(smell_count: int) -> int:
    """
    Calculate code smell score.
    Maximum score: 15
    """

    if smell_count == 0:
        return 15

    elif smell_count <= 2:
        return 12

    elif smell_count <= 5:
        return 8

    elif smell_count <= 10:
        return 4

    else:
        return 0


def calculate_static_score(
    complexity: float,
    total_code_lines: int,
    files_analyzed: int,
    has_tests: bool,
    secret_count: int,
    smell_count: int,
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
        secret_count
    )

    smell_score = calculate_smell_score(
        smell_count
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