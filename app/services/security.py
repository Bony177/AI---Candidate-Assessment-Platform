import re
from pathlib import Path


SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key)\s*[:=]\s*["\'][^"\']+["\']'),
    re.compile(r'(?i)(secret[_-]?key)\s*[:=]\s*["\'][^"\']+["\']'),
    re.compile(r'(?i)(password)\s*[:=]\s*["\'][^"\']+["\']'),
    re.compile(r'(?i)(access[_-]?token)\s*[:=]\s*["\'][^"\']+["\']'),
]


def scan_file_for_secrets(file_path: Path) -> list:

    findings = []

    try:
        lines = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        ).splitlines()

    except Exception:
        return findings

    for line_number, line in enumerate(lines, start=1):

        for pattern in SECRET_PATTERNS:

            if pattern.search(line):

                findings.append({
                    "file": str(file_path),
                    "line": line_number,
                    "type": "potential_secret",
                })

                break

    return findings