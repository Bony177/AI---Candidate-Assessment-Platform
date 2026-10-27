
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
