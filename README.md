# GitHub Candidate Assessment Engine - Backend

An automated evaluation pipeline that ingests GitHub metadata, clones selected repositories for static analysis, and generates candidate scoring reports.

## Tech Stack
- **Framework:** FastAPI (Python 3.10+)
- **Data Ingestion:** GitHub GraphQL API
- **Task Orchestration:** Asynchronous Background Tasks
- **HTTP Client:** HTTPX (Async)

## Project Structure
```text
├── app/
│   ├── api/          # Route handlers & endpoints
│   ├── services/     # GitHub GraphQL & Repo cloning services
│   └── main.py       # FastAPI application entry point
├── .env.example      # Sample environment configuration
├── .gitignore
├── requirements.txt
└── README.md
```

## Gitleaks security scanning

Install Gitleaks v8.19 or newer separately from Python dependencies and make
the `gitleaks` executable available on `PATH`. The application uses Gitleaks'
`git` mode for repositories with Git metadata and `dir` mode otherwise.
Full-history scoring requires a complete clone. Shallow clones and
working-tree-only scans are reported as partial and receive 0/20 for Security
rather than being treated as clean.

Gitleaks' standard JSON output does not provide credential verification or
severity. Findings are treated as potential and unverified. The application
uses an explicit rule-ID severity policy with an `unclassified` fallback;
Gitleaks allowlists are honored, so only findings emitted by the scan are
counted. A completed scan with no findings scores 20/20, but is not proof that
the repository is entirely secure. Secret and match values are not included
in the assessment report.

Security deductions per unique finding are Critical: 10, High: 6, Medium: 3,
Low: 1, and Unclassified: 3. The score is `max(0, 20 - total deductions)`;
incomplete scans receive 0/20 and are explicitly marked incomplete or failed.
The initial rule-ID policy maps `aws-access-token`, `aws-secret-access-key`,
and `private-key` to Critical; `github-pat` and `gitlab-pat` to High; and
`generic-api-key` to Medium. All other rule IDs are Unclassified until reviewed.

Set `GITLEAKS_BIN` only when the executable is not named `gitleaks` on `PATH`.

## Source-file analysis coverage

Each repository analysis report includes an `analysis_coverage` section.
Coverage is calculated as successfully analyzed supported source files divided
by all supported source files discovered by the static analyzer, multiplied by
100, and rounded to one decimal place. The existing analyzer exclusions and
supported extensions define that file scope. A repository with no supported
files reports a `no_supported_files` status and an unavailable percentage.

The completeness status is `complete` when every discovered supported file
passes its static-analysis stages, `partial` when any file is skipped or
fails, and `no_supported_files` when none are eligible. Repository-level
analysis failures report `failed`. This file-analysis completeness is separate
from the Gitleaks security-scan status and the existing weighted quality score.
Per-file details contain repository-relative paths and concise reasons only.

Retrieve the persisted coverage data from the existing
`GET /api/v1/report/{task_id}` endpoint after the task completes.
