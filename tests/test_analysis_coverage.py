import asyncio
import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import analyzer, job_manager
from app.services.analyzer import (
    _build_analysis_coverage,
    analyze_repository,
)
from app.services.job_manager import JOBS_DB
from app.services.scoring import calculate_static_score


client = TestClient(app)


def _complete_security_scan():
    return {
        "tool": "gitleaks",
        "status": "complete",
        "scan_mode": "dir",
        "history_status": "unavailable",
        "finding_count": 0,
        "findings": [],
    }


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def test_all_supported_languages_are_counted_as_analyzed(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    sources = {
        "main.py": "value = 1\n",
        "main.js": "const value = 1;\n",
        "main.jsx": "const View = () => <div />;\n",
        "main.ts": "const value: number = 1;\n",
        "main.tsx": "const View = () => <div />;\n",
    }
    for path, source in sources.items():
        (repo / path).write_text(source, encoding="utf-8")
    monkeypatch.setattr(
        analyzer,
        "scan_repository_with_gitleaks",
        lambda _: _complete_security_scan(),
    )

    result = analyze_repository(str(repo))
    coverage = result["analysis_coverage"]

    assert coverage["supported_files_discovered"] == 5
    assert coverage["files_analyzed"] == 5
    assert coverage["files_skipped"] == 0
    assert coverage["files_failed"] == 0
    assert coverage["coverage_percentage"] == 100.0
    assert coverage["status"] == "complete"
    assert {file["language"] for file in coverage["file_details"]} == {
        "Python",
        "JavaScript",
        "JSX",
        "TypeScript",
        "TSX",
    }


def test_python_parse_failure_is_reported_without_exposing_local_paths(
    tmp_path,
    monkeypatch,
):
    repo = _make_repo(tmp_path)
    (repo / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    monkeypatch.setattr(
        analyzer,
        "scan_repository_with_gitleaks",
        lambda _: _complete_security_scan(),
    )

    result = analyze_repository(str(repo))
    coverage = result["analysis_coverage"]
    serialized = json.dumps(result)

    assert coverage["status"] == "partial"
    assert coverage["files_failed"] == 1
    assert coverage["files_analyzed"] == 0
    assert coverage["coverage_percentage"] == 0.0
    assert coverage["file_details"][0]["stage"] == "python_ast"
    assert coverage["file_details"][0]["reason"] == "Python parsing failed."
    assert str(tmp_path) not in serialized


def test_tree_sitter_parse_failure_is_reported(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "broken.js").write_text("const = ;\n", encoding="utf-8")
    monkeypatch.setattr(
        analyzer,
        "scan_repository_with_gitleaks",
        lambda _: _complete_security_scan(),
    )

    coverage = analyze_repository(str(repo))["analysis_coverage"]

    assert coverage["status"] == "partial"
    assert coverage["files_failed"] == 1
    assert coverage["file_details"][0]["stage"] == "tree_sitter"
    assert (
        coverage["file_details"][0]["reason"]
        == "JavaScript/TypeScript parsing failed."
    )


def test_code_smell_parse_error_does_not_count_as_analyzed(
    tmp_path,
    monkeypatch,
):
    repo = _make_repo(tmp_path)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        analyzer,
        "detect_code_smells",
        lambda _: [{
            "type": "parse_error",
            "message": "Do not include raw parser output.",
        }],
    )
    monkeypatch.setattr(
        analyzer,
        "scan_repository_with_gitleaks",
        lambda _: _complete_security_scan(),
    )

    result = analyze_repository(str(repo))
    coverage = result["analysis_coverage"]

    assert coverage["files_analyzed"] == 0
    assert coverage["files_failed"] == 1
    assert coverage["file_details"][0]["stage"] == "code_smells"
    assert "Do not include raw parser output." not in json.dumps(result)


def test_coverage_aggregation_handles_analyzed_skipped_and_failed_files():
    coverage = _build_analysis_coverage([
        {"path": "ok.py", "language": "Python", "status": "analyzed"},
        {"path": "skip.js", "language": "JavaScript", "status": "skipped"},
        {"path": "bad.ts", "language": "TypeScript", "status": "failed"},
    ])

    assert coverage["supported_files_discovered"] == 3
    assert coverage["files_analyzed"] == 1
    assert coverage["files_skipped"] == 1
    assert coverage["files_failed"] == 1
    assert coverage["coverage_percentage"] == 33.3
    assert coverage["status"] == "partial"


def test_coverage_rounds_percentage_to_one_decimal_place():
    coverage = _build_analysis_coverage([
        {"path": "one.py", "status": "analyzed"},
        {"path": "two.py", "status": "analyzed"},
        {"path": "three.py", "status": "failed"},
    ])

    assert coverage["coverage_percentage"] == 66.7


def test_duplicate_paths_are_counted_once_and_failure_wins():
    coverage = _build_analysis_coverage([
        {"path": "same.py", "status": "analyzed"},
        {"path": "same.py", "status": "failed", "reason": "Parse failed."},
    ])

    assert coverage["supported_files_discovered"] == 1
    assert coverage["files_analyzed"] == 0
    assert coverage["files_failed"] == 1


def test_zero_supported_files_has_unavailable_coverage(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "README.md").write_text("documentation\n", encoding="utf-8")
    (repo / "Main.java").write_text("class Main {}", encoding="utf-8")
    monkeypatch.setattr(
        analyzer,
        "scan_repository_with_gitleaks",
        lambda _: _complete_security_scan(),
    )

    result = analyze_repository(str(repo))
    coverage = result["analysis_coverage"]

    assert coverage["supported_files_discovered"] == 0
    assert coverage["files_analyzed"] == 0
    assert coverage["coverage_percentage"] is None
    assert coverage["status"] == "no_supported_files"


def test_unsupported_and_excluded_files_do_not_enter_the_denominator(
    tmp_path,
    monkeypatch,
):
    repo = _make_repo(tmp_path)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "Other.java").write_text("class Other {}", encoding="utf-8")
    (repo / "test_app.py").write_text("value = 2\n", encoding="utf-8")
    ignored = repo / "node_modules"
    ignored.mkdir()
    (ignored / "vendor.py").write_text("value = 3\n", encoding="utf-8")
    monkeypatch.setattr(
        analyzer,
        "scan_repository_with_gitleaks",
        lambda _: _complete_security_scan(),
    )

    coverage = analyze_repository(str(repo))["analysis_coverage"]

    assert coverage["supported_files_discovered"] == 1
    assert coverage["files_analyzed"] == 1
    assert [file["path"] for file in coverage["file_details"]] == ["app.py"]


def test_missing_failure_reasons_are_optional():
    coverage = _build_analysis_coverage([
        {"path": "skipped.py", "status": "skipped"},
        {"path": "failed.py", "status": "failed"},
    ])

    assert coverage["status"] == "partial"
    assert all("reason" not in file for file in coverage["file_details"])


def test_analysis_coverage_is_persisted_in_report_and_api(
    tmp_path,
    monkeypatch,
):
    repo = _make_repo(tmp_path)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    security_scan = _complete_security_scan()
    monkeypatch.setattr(
        analyzer,
        "scan_repository_with_gitleaks",
        lambda _: security_scan,
    )

    async def fetch_github_data(_):
        return {
            "login": "candidate",
            "avatarUrl": None,
            "contributionsCollection": {
                "contributionCalendar": {"totalContributions": 4}
            },
            "repositories": {
                "nodes": [{
                    "name": "repo",
                    "url": "https://github.com/candidate/repo",
                    "isFork": False,
                    "isArchived": False,
                    "owner": {"login": "candidate"},
                }]
            },
        }

    async def no_wait(_):
        return None

    monkeypatch.setattr(job_manager, "fetch_github_data", fetch_github_data)
    monkeypatch.setattr(
        job_manager,
        "clone_repositories",
        lambda *_args, **_kwargs: {"repo": str(repo)},
    )
    monkeypatch.setattr(job_manager, "cleanup_cloned_repos", lambda _: None)
    monkeypatch.setattr(job_manager.asyncio, "sleep", no_wait)
    task_id = "coverage-report-test"
    JOBS_DB[task_id] = {"status": "QUEUED", "error": None, "report": None}

    asyncio.run(job_manager.run_assessment_pipeline(
        task_id,
        "candidate",
        None,
        ["repo"],
    ))

    report = JOBS_DB[task_id]["report"]
    repository = report["repositories"][0]
    analysis = repository["analysis"]
    response = client.get(f"/api/v1/report/{task_id}")

    assert JOBS_DB[task_id]["status"] == "COMPLETED"
    assert response.status_code == 200
    assert response.json()["repositories"][0]["analysis"][
        "analysis_coverage"
    ] == analysis["analysis_coverage"]
    assert repository["analysis"]["security_scan"] == security_scan
    assert analysis["static_score"] == calculate_static_score(
        complexity=analysis["average_complexity"],
        total_code_lines=analysis["total_code_lines"],
        files_analyzed=analysis["files_analyzed"],
        has_tests=analysis["tests"]["has_tests"],
        security_findings=analysis["security_scan"]["findings"],
        security_scan_status=analysis["security_scan"]["status"],
        warning_density_per_1000_loc=analysis[
            "warning_density_per_1000_loc"
        ],
    )


def test_report_endpoint_does_not_return_coverage_while_running():
    task_id = "coverage-report-pending-test"
    JOBS_DB[task_id] = {
        "status": "RUNNING_STATIC_ANALYSIS",
        "report": None,
        "error": None,
    }

    response = client.get(f"/api/v1/report/{task_id}")

    assert response.status_code == 400
    assert "Report is not ready yet" in response.json()["detail"]
