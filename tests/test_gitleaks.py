import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import gitleaks
from app.services.analyzer import analyze_repository
from app.services.job_manager import JOBS_DB
from app.services.repo_cloner import (
    cleanup_cloned_repos,
    clone_repositories,
)
from app.services.scoring import (
    calculate_security_score,
    calculate_static_score,
)


client = TestClient(app)
SECRET_VALUE = "do-not-return-this-secret"


def _make_repo(tmp_path, git=True, shallow=False):
    repo = tmp_path / "repo"
    repo.mkdir()
    if git:
        git_dir = repo / ".git"
        git_dir.mkdir()
        if shallow:
            (git_dir / "shallow").write_text("commit\n", encoding="utf-8")
    return repo


def _finding(
    rule_id="generic-api-key",
    fingerprint="same-finding",
    file="src/app.py",
    line=12,
):
    return {
        "RuleID": rule_id,
        "Description": f"unsafe description containing {SECRET_VALUE}",
        "File": file,
        "StartLine": line,
        "Fingerprint": fingerprint,
        "Secret": SECRET_VALUE,
        "Match": f"API_KEY={SECRET_VALUE}",
        "Tags": [],
    }


def _mock_gitleaks(monkeypatch, payload, returncode=0):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] == "git":
            return SimpleNamespace(returncode=0)
        assert "--redact=100" in command
        assert "--report-path=-" in command
        return SimpleNamespace(
            returncode=returncode,
            stdout=json.dumps(payload),
        )

    monkeypatch.setattr(gitleaks.shutil, "which", lambda _: "gitleaks.exe")
    monkeypatch.setattr(gitleaks.subprocess, "run", fake_run)
    return commands


def test_clean_complete_scan_and_zero_findings_score(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    _mock_gitleaks(monkeypatch, [], returncode=0)

    result = gitleaks.scan_repository_with_gitleaks(repo)

    assert result["status"] == "complete"
    assert result["history_status"] == "complete"
    assert result["finding_count"] == 0
    assert result["findings"] == []
    assert calculate_security_score(result["findings"], result["status"]) == 20


def test_gitleaks_finding_is_sanitized_and_nonzero_findings_exit_is_success(
    tmp_path,
    monkeypatch,
):
    repo = _make_repo(tmp_path)
    _mock_gitleaks(monkeypatch, [_finding()], returncode=1)

    result = gitleaks.scan_repository_with_gitleaks(repo)
    serialized = json.dumps(result)

    assert result["status"] == "complete"
    assert result["finding_count"] == 1
    assert result["findings"][0] == {
        "rule_id": "generic-api-key",
        "severity": "medium",
        "severity_source": "application_rule_map",
        "file": "src/app.py",
        "line": 12,
        "description": (
            "Potential secret detected by Gitleaks rule generic-api-key."
        ),
    }
    assert SECRET_VALUE not in serialized
    assert "unsafe description" not in serialized
    assert calculate_security_score(result["findings"], result["status"]) == 17


def test_multiple_severity_findings_score_cumulatively(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    payload = [
        _finding("aws-access-token", "critical", "a.py", 1),
        _finding("github-pat", "high", "b.py", 2),
        _finding("generic-api-key", "medium", "c.py", 3),
        _finding("unknown-rule", "unknown", "d.py", 4),
    ]
    _mock_gitleaks(monkeypatch, payload, returncode=1)

    result = gitleaks.scan_repository_with_gitleaks(repo)

    assert [finding["severity"] for finding in result["findings"]] == [
        "critical",
        "high",
        "medium",
        "unclassified",
    ]
    assert calculate_security_score(result["findings"], result["status"]) == 0


def test_duplicate_fingerprints_are_counted_once(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    _mock_gitleaks(
        monkeypatch,
        [
            _finding(fingerprint="duplicate"),
            _finding(fingerprint="duplicate", line=99),
            _finding(fingerprint="distinct", line=13),
        ],
        returncode=1,
    )

    result = gitleaks.scan_repository_with_gitleaks(repo)

    assert result["finding_count"] == 2
    assert calculate_security_score(result["findings"], result["status"]) == 14


def test_security_scoring_boundaries_and_incomplete_scan():
    assert calculate_security_score([], "complete") == 20
    assert calculate_security_score([{"severity": "critical"}], "complete") == 10
    assert calculate_security_score([{"severity": "high"}], "complete") == 14
    assert calculate_security_score([{"severity": "medium"}], "complete") == 17
    assert calculate_security_score([{"severity": "low"}], "complete") == 19
    assert calculate_security_score([{"severity": "unclassified"}], "complete") == 17
    assert calculate_security_score(
        [{"severity": "high"}, {"severity": "high"}],
        "complete",
    ) == 8
    assert calculate_security_score(
        [{"severity": "high"}, {"severity": "medium"}],
        "complete",
    ) == 11
    assert calculate_security_score(
        [{"severity": "critical"}, {"severity": "critical"}],
        "complete",
    ) == 0
    assert calculate_security_score([], "partial") == 0
    assert calculate_security_score([], "failed") == 0


def test_static_score_preserves_other_categories_and_100_point_max():
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


def test_incomplete_scan_cannot_award_full_security_score():
    score = calculate_static_score(
        complexity=5,
        total_code_lines=100,
        files_analyzed=1,
        has_tests=True,
        security_findings=[],
        security_scan_status="failed",
        warning_density_per_1000_loc=0,
    )

    assert score["breakdown"]["security"] == 0
    assert score["total_score"] == 80


def test_analyzer_passes_gitleaks_result_into_static_score(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path, git=False)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    scan = {
        "tool": "gitleaks",
        "status": "complete",
        "history_status": "unavailable",
        "error_code": None,
        "finding_count": 1,
        "findings": [
            {
                "rule_id": "generic-api-key",
                "severity": "medium",
                "severity_source": "application_rule_map",
                "file": "app.py",
                "line": 1,
                "description": "Potential secret detected by Gitleaks rule generic-api-key.",
            }
        ],
    }
    monkeypatch.setattr(
        "app.services.analyzer.scan_repository_with_gitleaks",
        lambda _: scan,
    )

    result = analyze_repository(str(repo))

    assert result["security_scan"] == scan
    assert result["potential_secrets"] == scan["findings"]
    assert result["static_score"]["breakdown"]["security"] == 17
    assert result["static_score"]["total_score"] == sum(
        result["static_score"]["breakdown"].values()
    )
    assert result["files"][0]["secrets"] == scan["findings"]


def test_missing_executable_fails_closed(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    monkeypatch.setattr(gitleaks.shutil, "which", lambda _: None)

    result = gitleaks.scan_repository_with_gitleaks(repo)

    assert result["status"] == "failed"
    assert result["error_code"] == "executable_unavailable"
    assert result["finding_count"] == 0
    assert calculate_security_score(result["findings"], result["status"]) == 0


def test_timeout_does_not_expose_subprocess_output(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)

    def timeout_run(*args, **kwargs):
        if args[0][0] == "git":
            return SimpleNamespace(returncode=0)
        raise gitleaks.subprocess.TimeoutExpired(
            args[0],
            timeout=1,
            output=SECRET_VALUE,
        )

    monkeypatch.setattr(gitleaks.shutil, "which", lambda _: "gitleaks.exe")
    monkeypatch.setattr(gitleaks.subprocess, "run", timeout_run)

    result = gitleaks.scan_repository_with_gitleaks(repo)

    assert result["status"] == "failed"
    assert result["error_code"] == "scan_timeout"
    assert SECRET_VALUE not in json.dumps(result)


def test_malformed_report_is_failed_not_clean(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)

    def malformed_run(command, **kwargs):
        if command[0] == "git":
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=0, stdout="not JSON")

    monkeypatch.setattr(gitleaks.shutil, "which", lambda _: "gitleaks.exe")
    monkeypatch.setattr(gitleaks.subprocess, "run", malformed_run)

    result = gitleaks.scan_repository_with_gitleaks(repo)

    assert result["status"] == "failed"
    assert result["error_code"] == "report_invalid"
    assert result["finding_count"] == 0
    assert calculate_security_score(result["findings"], result["status"]) == 0


def test_non_finding_nonzero_exit_is_failed(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    _mock_gitleaks(monkeypatch, [], returncode=2)

    result = gitleaks.scan_repository_with_gitleaks(repo)

    assert result["status"] == "failed"
    assert result["error_code"] == "scan_nonzero_exit"
    assert calculate_security_score(result["findings"], result["status"]) == 0


def test_oversized_output_is_incomplete_not_clean(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    monkeypatch.setattr(gitleaks, "MAX_REPORT_BYTES", 5)

    def oversized_run(command, **kwargs):
        if command[0] == "git":
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=0, stdout="123456")

    monkeypatch.setattr(gitleaks.shutil, "which", lambda _: "gitleaks.exe")
    monkeypatch.setattr(gitleaks.subprocess, "run", oversized_run)

    result = gitleaks.scan_repository_with_gitleaks(repo)

    assert result["status"] == "failed"
    assert result["error_code"] == "report_too_large"
    assert calculate_security_score(result["findings"], result["status"]) == 0


@pytest.mark.parametrize(
    ("git", "shallow", "expected_status", "expected_history"),
    [
        (False, False, "partial", "unavailable"),
        (True, True, "partial", "shallow"),
    ],
)
def test_missing_or_shallow_history_is_partial(
    tmp_path,
    monkeypatch,
    git,
    shallow,
    expected_status,
    expected_history,
):
    repo = _make_repo(tmp_path, git=git, shallow=shallow)
    commands = _mock_gitleaks(monkeypatch, [])

    result = gitleaks.scan_repository_with_gitleaks(repo)

    expected_mode = "git" if git else "dir"
    gitleaks_command = next(
        command for command in commands if command[0] != "git"
    )
    assert gitleaks_command[1] == expected_mode
    assert result["status"] == expected_status
    assert result["history_status"] == expected_history
    assert calculate_security_score(result["findings"], result["status"]) == 0


def test_empty_git_repository_without_head_scans_working_tree_as_partial(
    tmp_path,
    monkeypatch,
):
    repo = _make_repo(tmp_path)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] == "git":
            return SimpleNamespace(returncode=128)
        return SimpleNamespace(returncode=0, stdout="[]")

    monkeypatch.setattr(gitleaks.shutil, "which", lambda _: "gitleaks.exe")
    monkeypatch.setattr(gitleaks.subprocess, "run", fake_run)

    result = gitleaks.scan_repository_with_gitleaks(repo)

    assert commands[-1][1] == "dir"
    assert result["status"] == "partial"
    assert result["history_status"] == "unavailable"
    assert result["finding_count"] == 0


def test_analyzer_does_not_fall_back_to_regex_when_gitleaks_is_missing(
    tmp_path,
    monkeypatch,
):
    repo = _make_repo(tmp_path, git=False)
    (repo / "app.py").write_text(
        'API_KEY = "test-value"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(gitleaks.shutil, "which", lambda _: None)

    result = analyze_repository(str(repo))

    assert result["security_scan"]["status"] == "failed"
    assert result["security_scan"]["error_code"] == "executable_unavailable"
    assert result["potential_secrets"] == []
    assert result["static_score"]["breakdown"]["security"] == 0


def test_repository_cloner_fetches_full_history(monkeypatch):
    observed_commands = []

    def fake_run(command, **kwargs):
        observed_commands.append(command)

    monkeypatch.setattr(
        "app.services.repo_cloner.subprocess.run",
        fake_run,
    )
    cloned_paths = clone_repositories(
        [
            {
                "name": "sample",
                "owner": {"login": "candidate"},
                "url": "https://github.com/candidate/sample",
            }
        ]
    )
    try:
        assert len(observed_commands) == 1
        assert "clone" in observed_commands[0]
        assert "--depth" not in observed_commands[0]
        assert "https://github.com/candidate/sample.git" in observed_commands[0]
    finally:
        cleanup_cloned_repos(cloned_paths)


def test_report_endpoint_returns_sanitized_security_metadata():
    task_id = "gitleaks-api-contract-test"
    finding = {
        "rule_id": "generic-api-key",
        "severity": "medium",
        "severity_source": "application_rule_map",
        "file": "src/app.py",
        "line": 12,
        "description": "Potential secret detected by Gitleaks rule generic-api-key.",
    }
    JOBS_DB[task_id] = {
        "status": "COMPLETED",
        "report": {
            "repositories": [
                {
                    "name": "sample",
                    "status": "analyzed",
                    "analysis": {
                        "security_scan": {
                            "tool": "gitleaks",
                            "status": "complete",
                            "history_status": "complete",
                            "finding_count": 1,
                            "findings": [finding],
                        },
                        "static_score": {
                            "total_score": 97,
                            "breakdown": {"security": 17},
                        },
                    },
                }
            ]
        },
    }
    try:
        response = client.get(f"/api/v1/report/{task_id}")
    finally:
        JOBS_DB.pop(task_id, None)

    assert response.status_code == 200
    analysis = response.json()["repositories"][0]["analysis"]
    assert analysis["security_scan"]["findings"] == [finding]
    assert analysis["static_score"]["breakdown"]["security"] == 17
