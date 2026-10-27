
"""
Unit tests for the warning_density_per_1000_loc metric.

Formula:
    warning_density_per_1000_loc = (total_smells / total_code_lines) * 1000

Zero-LOC convention:
    Density = 0 with loc_status explaining that zero LOC does not
    indicate excellent code quality.
"""

import tempfile
import shutil
import textwrap
from pathlib import Path

from app.services.analyzer import analyze_repository
from app.services.scoring import (
    calculate_code_smell_score,
    calculate_static_score,
)


# ----------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------

def _make_repo(*files: tuple[str, str]) -> Path:
    """Create a temporary repository with the given files."""
    tmp = Path(tempfile.mkdtemp())

    for relative, content in files:
        full = tmp / relative
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(textwrap.dedent(content), encoding="utf-8")

    return tmp


class TestCodeSmellScoring:
    """Tests for warning-density-based Code Smells scoring."""

    def test_density_threshold_scores(self):
        """Density thresholds map to the requested marks out of 15."""

        test_cases = [
            (0, 15),
            (2, 15),
            (2.1, 12),
            (5, 12),
            (10, 9),
            (20, 6),
            (40, 3),
            (40.01, 0),
        ]

        for density, expected_score in test_cases:
            assert calculate_code_smell_score(density, 1000) == expected_score

    def test_zero_loc_scores_zero_regardless_of_density(self):
        """Zero LOC must not receive a perfect score from zero density."""

        assert calculate_code_smell_score(0, 0) == 0

    def test_requested_density_regressions_and_other_categories_unchanged(self):
        """Density selects the smell score without changing other categories."""

        cases = [
            (7.49, 9),
            (2.2, 12),
            (0, 15),
        ]
        other_categories = {
            "complexity": 25,
            "structure": 20,
            "testing": 20,
            "security": 20,
        }

        for density, expected_smell_score in cases:
            assert (
                calculate_code_smell_score(density, 1000)
                == expected_smell_score
            )

            score = calculate_static_score(
                complexity=5,
                total_code_lines=1000,
                files_analyzed=10,
                has_tests=True,
                security_findings=[],
                security_scan_status="complete",
                warning_density_per_1000_loc=density,
            )

            assert score["breakdown"]["code_smells"] == expected_smell_score
            assert {
                category: score["breakdown"][category]
                for category in other_categories
            } == other_categories
            assert score["total_score"] == sum(score["breakdown"].values())

        assert calculate_code_smell_score(0, 0) == 0
        zero_loc_score = calculate_static_score(
            complexity=5,
            total_code_lines=0,
            files_analyzed=1,
            has_tests=True,
            security_findings=[],
            security_scan_status="complete",
            warning_density_per_1000_loc=0,
        )
        assert zero_loc_score["breakdown"]["code_smells"] == 0
        assert zero_loc_score["total_score"] == sum(
            zero_loc_score["breakdown"].values()
        )

    def test_higher_density_never_increases_score(self):
        """The score is non-increasing as warning density rises."""

        densities = [0, 2, 2.1, 5, 5.1, 10, 10.1, 20, 20.1, 40, 40.1]
        scores = [
            calculate_code_smell_score(density, 1000)
            for density in densities
        ]

        assert all(
            earlier >= later
            for earlier, later in zip(scores, scores[1:])
        )

    def test_code_smell_score_contributes_to_static_total(self):
        """The density-based score is included in the existing total."""

        score = calculate_static_score(
            complexity=5,
            total_code_lines=100,
            files_analyzed=1,
            has_tests=True,
            security_findings=[],
            security_scan_status="complete",
            warning_density_per_1000_loc=2.1,
        )

        assert score["breakdown"] == {
            "complexity": 25,
            "structure": 20,
            "testing": 20,
            "security": 20,
            "code_smells": 12,
        }
        assert score["total_score"] == sum(score["breakdown"].values()) == 97

    def test_all_categories_still_total_one_hundred(self):
        """The category maxima retain the existing total of 100 marks."""

        score = calculate_static_score(
            complexity=5,
            total_code_lines=100,
            files_analyzed=1,
            has_tests=True,
            security_findings=[],
            security_scan_status="complete",
            warning_density_per_1000_loc=0,
        )

        assert score["breakdown"] == {
            "complexity": 25,
            "structure": 20,
            "testing": 20,
            "security": 20,
            "code_smells": 15,
        }
        assert score["total_score"] == 100


# ----------------------------------------------------------------
# TESTS
# ----------------------------------------------------------------

class TestWarningDensityPerThousandLOC:
    """Tests for the warning-density metric."""

    def test_standard_density_20_warnings_2000_loc(self):
        """20 smells / 2,000 LOC = 10.0 smells per 1,000 LOC."""

        repo = _make_repo(
            *(
                (
                    f"mod_{i}.py",
                    f"def big_func_{i}():\n"
                    + "".join(f"    x{j} = {j}\n" for j in range(53))
                    + "    return None\n"
                    + "".join(
                        f"val_{i}_{k} = {k}\n" for k in range(45)
                    ),
                )
                for i in range(20)
            )
        )

        try:
            result = analyze_repository(str(repo))

            assert result["total_smells"] == 20
            assert result["total_code_lines"] == 2000
            assert result["warning_density_per_1000_loc"] == 10.0
            assert result["loc_status"] == "ok"

        finally:
            shutil.rmtree(repo)

    def test_zero_warnings_2000_loc(self):
        """0 smells / 2,000 LOC = 0.0."""

        repo = _make_repo(
            *(
                (
                    f"clean_{i}.py",
                    "".join(f"x{j} = {j}\n" for j in range(100)),
                )
                for i in range(20)
            )
        )

        try:
            result = analyze_repository(str(repo))

            assert result["total_smells"] == 0
            assert result["total_code_lines"] == 2000
            assert result["warning_density_per_1000_loc"] == 0
            assert result["loc_status"] == "ok"
            assert result["static_score"]["breakdown"]["code_smells"] == 15
            assert result["static_score"]["total_score"] == sum(
                result["static_score"]["breakdown"].values()
            )

        finally:
            shutil.rmtree(repo)

    def test_zero_loc_returns_density_zero_with_status(self):
        """An empty repository must not cause division by zero."""

        repo = _make_repo()

        try:
            result = analyze_repository(str(repo))

            assert result["total_code_lines"] == 0
            assert result["warning_density_per_1000_loc"] == 0
            assert "zero_loc" in result["loc_status"]
            assert result["static_score"]["breakdown"]["code_smells"] == 0

        finally:
            shutil.rmtree(repo)

    def test_aggregation_across_different_file_sizes(self):
        """
        File A: 1,000 LOC.
        File B: 9,000 LOC.

        Expected total: 22 smells / 10,000 LOC * 1,000 = 2.0.
        Diagnostic output identifies the actual smell findings.
        """

        def _make_file_content(
            file_id: str,
            code_lines: int,
            smell_count: int,
        ) -> str:
            """Generate a Python file with long functions and padding."""

            lines = []
            lines_used = 0

            # Each generated function has 55 lines.
            for f_idx in range(smell_count):
                lines.append(f"def long_func_{file_id}_{f_idx}():\n")

                for j in range(53):
                    lines.append(f"    v{j} = {j}\n")

                lines.append("    return None\n")
                lines_used += 55

            # Pad to the requested total line count.
            remaining = code_lines - lines_used

            for k in range(remaining):
                lines.append(f"pad_{file_id}_{k} = {k}\n")

            return "".join(lines)

        file_a = _make_file_content("a", 1000, 10)
        file_b = _make_file_content("b", 9000, 10)

        repo = _make_repo(
            ("file_a.py", file_a),
            ("file_b.py", file_b),
        )

        try:
            result = analyze_repository(str(repo))

            # Verify raw counts
            assert result["total_code_lines"] == 10_000
            assert result["total_smells"] == 22

            # Verify aggregated density
            assert result["warning_density_per_1000_loc"] == 2.2
            assert result["loc_status"] == "ok"
            assert result["static_score"]["breakdown"]["code_smells"] == 12
            assert result["static_score"]["total_score"] == sum(
                result["static_score"]["breakdown"].values()
            )

        finally:
            shutil.rmtree(repo)

    def test_empty_repository(self):
        """An empty repository has zero files, LOC, and smells."""

        repo = _make_repo()

        try:
            result = analyze_repository(str(repo))

            assert result["files_analyzed"] == 0
            assert result["total_code_lines"] == 0
            assert result["total_smells"] == 0
            assert result["warning_density_per_1000_loc"] == 0
            assert "zero_loc" in result["loc_status"]

        finally:
            shutil.rmtree(repo)

    def test_density_fields_always_present(self):
        """The density fields must always be present."""

        repo = _make_repo(("hello.py", "print('hello')\n"))

        try:
            result = analyze_repository(str(repo))

            assert "warning_density_per_1000_loc" in result
            assert "loc_status" in result

            assert isinstance(
                result["warning_density_per_1000_loc"],
                (int, float),
            )
            assert isinstance(result["loc_status"], str)

        finally:
            shutil.rmtree(repo)

    def test_existing_fields_preserved(self):
        """Existing analyzer response fields must remain available."""

        repo = _make_repo(("app.py", "x = 1\n"))

        try:
            result = analyze_repository(str(repo))

            expected_keys = [
                "repository",
                "files_analyzed",
                "total_code_lines",
                "total_functions",
                "total_classes",
                "total_complexity",
                "average_complexity",
                "total_smells",
                "warning_density_per_1000_loc",
                "loc_status",
                "potential_secrets",
                "tests",
                "static_score",
                "files",
            ]

            for key in expected_keys:
                assert key in result, f"Missing expected key: {key}"

            assert "total_score" in result["static_score"]
            assert "breakdown" in result["static_score"]

        finally:
            shutil.rmtree(repo)

    def test_scoring_not_altered_by_density(self):
        """The existing score categories must remain unchanged."""

        repo = _make_repo(("main.py", "x = 1\n"))

        try:
            result = analyze_repository(str(repo))
            breakdown = result["static_score"]["breakdown"]

            expected_categories = {
                "complexity",
                "structure",
                "testing",
                "security",
                "code_smells",
            }

            assert set(breakdown.keys()) == expected_categories

        finally:
            shutil.rmtree(repo)
