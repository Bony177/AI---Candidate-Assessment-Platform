import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

GITLEAKS_TIMEOUT_SECONDS = 300
PROCESS_TIMEOUT_SECONDS = GITLEAKS_TIMEOUT_SECONDS + 30
MAX_REPORT_BYTES = 10 * 1024 * 1024
MAX_FINDINGS = 10_000
SAFE_RULE_ID = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

# Gitleaks does not emit severity. These reviewed rule-ID classifications are
# application policy; unmatched rules use the documented unclassified weight.
RULE_SEVERITY_BY_ID = {
    "aws-access-token": "critical",
    "aws-secret-access-key": "critical",
    "private-key": "critical",
    "github-pat": "high",
    "gitlab-pat": "high",
    "generic-api-key": "medium",
}


def _failure(
    status: str,
    history_status: str,
    error_code: str,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    safe_findings = findings or []
    return {
        "tool": "gitleaks",
        "status": status,
        "scan_mode": (
            "unavailable"
            if error_code == "invalid_source"
            else "git"
            if history_status in {"complete", "shallow"}
            else "dir"
        ),
        "history_status": history_status,
        "suppression_policy": "gitleaks_allowlists_honored",
        "error_code": error_code,
        "finding_count": len(safe_findings),
        "findings": safe_findings,
    }


def _safe_file_path(raw_file: Any, source: Path) -> str | None:
    if not isinstance(raw_file, str) or not raw_file.strip():
        return None

    path_text = raw_file.strip().replace("\\", "/")
    source_text = str(source.resolve()).replace("\\", "/").rstrip("/")
    if path_text.startswith(f"{source_text}/"):
        path_text = path_text[len(source_text) + 1 :]

    path_text = path_text.removeprefix("./")
    path_parts = path_text.split("/")
    if (
        not path_text
        or "\x00" in path_text
        or any(part in {"", ".", ".."} for part in path_parts)
    ):
        return None

    if re.match(r"^[A-Za-z]:/", path_text) or path_text.startswith("/"):
        return path_parts[-1]

    return path_text[:500]


def _sanitize_findings(
    payload: Any,
    source: Path,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("Gitleaks JSON must be a list.")

    findings = []
    seen = set()

    for raw_finding in payload:
        if not isinstance(raw_finding, dict):
            raise ValueError("Gitleaks finding must be an object.")

        raw_rule_id = raw_finding.get("RuleID")
        if not isinstance(raw_rule_id, str) or not SAFE_RULE_ID.fullmatch(
            raw_rule_id
        ):
            raise ValueError("Gitleaks finding has an invalid rule ID.")

        rule_id = raw_rule_id
        file_path = _safe_file_path(raw_finding.get("File"), source)
        raw_line = raw_finding.get("StartLine")
        line = (
            raw_line
            if isinstance(raw_line, int) and not isinstance(raw_line, bool)
            and raw_line > 0
            else None
        )

        fingerprint = raw_finding.get("Fingerprint")
        if isinstance(fingerprint, str) and fingerprint:
            identity = ("fingerprint", fingerprint)
        else:
            identity = ("metadata", rule_id, file_path, line)

        if identity in seen:
            continue
        seen.add(identity)

        severity = RULE_SEVERITY_BY_ID.get(rule_id.lower(), "unclassified")
        findings.append({
            "rule_id": rule_id,
            "severity": severity,
            "severity_source": (
                "application_rule_map"
                if severity != "unclassified"
                else "unclassified"
            ),
            "file": file_path,
            "line": line,
            "description": (
                f"Potential secret detected by Gitleaks rule {rule_id}."
            ),
        })

    findings.sort(
        key=lambda item: (
            item["file"] or "",
            item["line"] or 0,
            item["rule_id"],
        )
    )
    return findings


def _subprocess_environment() -> dict[str, str]:
    safe_keys = (
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
    )
    return {
        key: os.environ[key]
        for key in safe_keys
        if os.environ.get(key)
    }


def _git_scan_state(source: Path) -> tuple[str, str]:
    git_metadata = source / ".git"
    if not git_metadata.is_dir():
        return "dir", "unavailable"

    try:
        result = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "--verify", "HEAD"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            env=_subprocess_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return "dir", "unavailable"

    if result.returncode != 0:
        return "dir", "unavailable"

    if (git_metadata / "shallow").exists():
        return "git", "shallow"
    return "git", "complete"


def scan_repository_with_gitleaks(repo_path: str | Path) -> dict[str, Any]:
    """Scan repository history or, without Git metadata, its working tree."""

    source = Path(repo_path)
    if not source.is_dir():
        return _failure("failed", "unavailable", "invalid_source")

    scan_mode, history_status = _git_scan_state(source)

    executable_name = os.environ.get("GITLEAKS_BIN", "gitleaks")
    executable = shutil.which(executable_name)
    if not executable:
        return _failure("failed", history_status, "executable_unavailable")

    try:
        command = [
            executable,
            scan_mode,
            str(source),
            "--report-format",
            "json",
            "--report-path=-",
            "--redact=100",
            "--no-banner",
            f"--timeout={GITLEAKS_TIMEOUT_SECONDS}",
        ]

        try:
            result = subprocess.run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=PROCESS_TIMEOUT_SECONDS,
                env=_subprocess_environment(),
            )
        except subprocess.TimeoutExpired:
            return _failure("failed", history_status, "scan_timeout")
        except OSError:
            return _failure(
                "failed", history_status, "executable_unavailable"
            )

        report_text = result.stdout
        if not isinstance(report_text, str):
            return _failure("failed", history_status, "report_missing")
        if len(report_text.encode("utf-8")) > MAX_REPORT_BYTES:
            return _failure("failed", history_status, "report_too_large")

        try:
            payload = json.loads(report_text)
            if isinstance(payload, list) and len(payload) > MAX_FINDINGS:
                return _failure(
                    "failed", history_status, "too_many_findings"
                )
            findings = _sanitize_findings(payload, source)
        except (UnicodeError, json.JSONDecodeError, ValueError):
            return _failure("failed", history_status, "report_invalid")

        if result.returncode not in (0, 1):
            return _failure(
                "failed",
                history_status,
                "scan_nonzero_exit",
                findings,
            )
        if result.returncode == 1 and not findings:
            return _failure(
                "failed",
                history_status,
                "inconsistent_exit_status",
            )

        if history_status == "complete":
            status = "complete"
            error_code = None
        else:
            status = "partial"
            error_code = (
                "shallow_history"
                if history_status == "shallow"
                else "history_unavailable"
            )

        return {
            "tool": "gitleaks",
            "status": status,
            "scan_mode": scan_mode,
            "history_status": history_status,
            "suppression_policy": "gitleaks_allowlists_honored",
            "error_code": error_code,
            "finding_count": len(findings),
            "findings": findings,
        }
    except OSError:
        logger.warning("Unable to read Gitleaks scan output.")
        return _failure("failed", history_status, "report_read_error")
