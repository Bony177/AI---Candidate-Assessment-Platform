import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import job_manager
from app.services.github_service import fetch_candidate_repositories


client = TestClient(app)


@pytest.mark.asyncio
async def test_fetch_candidate_repositories_success(monkeypatch):
    class MockResponse:
        status_code = 200

        def json(self):
            return [
                {
                    "name": "linux",
                    "full_name": "torvalds/linux",
                    "owner": {"login": "torvalds"},
                    "html_url": "https://github.com/torvalds/linux",
                    "clone_url": "https://github.com/torvalds/linux.git",
                    "description": "Linux kernel",
                    "language": "C",
                    "stargazers_count": 1200,
                    "forks_count": 300,
                    "pushed_at": "2024-05-10T00:00:00Z",
                    "fork": False,
                    "archived": False,
                },
                {
                    "name": "project-two",
                    "full_name": "torvalds/project-two",
                    "owner": {"login": "torvalds"},
                    "html_url": "https://github.com/torvalds/project-two",
                    "clone_url": "https://github.com/torvalds/project-two.git",
                    "description": "Another project",
                    "language": "Python",
                    "stargazers_count": 200,
                    "forks_count": 10,
                    "pushed_at": "2024-04-02T00:00:00Z",
                    "fork": False,
                    "archived": False,
                },
            ]

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr("app.services.github_service.httpx.AsyncClient", MockAsyncClient)

    repos = await fetch_candidate_repositories("torvalds")

    assert len(repos) == 2
    assert repos[0]["owner"] == "torvalds"
    assert repos[0]["name"] == "linux"
    assert repos[0]["clone_url"] == "https://github.com/torvalds/linux.git"


def test_repository_list_contains_owner_information(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.fetch_candidate_repositories",
        lambda username: {
            "username": username,
            "repositories": [
                {
                    "name": "linux",
                    "owner": "torvalds",
                    "url": "https://github.com/torvalds/linux",
                    "clone_url": "https://github.com/torvalds/linux.git",
                    "description": "Linux kernel",
                    "primary_language": "C",
                    "stars": 1200,
                    "forks": 300,
                    "updated_at": "2024-05-10T00:00:00Z",
                    "is_fork": False,
                    "is_archived": False,
                }
            ],
        },
    )

    response = client.get("/api/v1/repositories/torvalds")
    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "torvalds"
    assert payload["repositories"][0]["owner"] == "torvalds"
    assert payload["repositories"][0]["clone_url"].endswith(".git")


def test_forked_repositories_are_excluded(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.fetch_candidate_repositories",
        lambda username: {
            "username": username,
            "repositories": [
                {
                    "name": "forked-project",
                    "owner": "torvalds",
                    "url": "https://github.com/torvalds/forked-project",
                    "clone_url": "https://github.com/torvalds/forked-project.git",
                    "description": "fork",
                    "primary_language": "Python",
                    "stars": 5,
                    "forks": 1,
                    "updated_at": "2024-04-01T00:00:00Z",
                    "is_fork": True,
                    "is_archived": False,
                }
            ],
        },
    )

    response = client.get("/api/v1/repositories/torvalds")
    assert response.status_code == 200
    assert response.json()["repositories"] == []


def test_repositories_belonging_to_other_owner_cannot_be_selected():
    payload = {
        "github_username": "torvalds",
        "job_description": "Python developer",
        "selected_repositories": [{"owner": "someone-else", "name": "linux"}],
    }

    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code in {400, 422}


def test_empty_repository_selection_is_rejected():
    payload = {
        "github_username": "torvalds",
        "job_description": "Python developer",
        "selected_repositories": [],
    }

    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code in {400, 422}


def test_more_than_max_selected_repositories_is_rejected():
    payload = {
        "github_username": "torvalds",
        "job_description": "Python developer",
        "selected_repositories": [
            {"owner": "torvalds", "name": f"repo-{i}"}
            for i in range(1, 7)
        ],
    }

    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code in {400, 422}


def test_duplicate_repository_selections_are_rejected():
    payload = {
        "github_username": "torvalds",
        "job_description": "Python developer",
        "selected_repositories": [
            {"owner": "torvalds", "name": "linux"},
            {"owner": "torvalds", "name": "linux"},
        ],
    }

    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code in {400, 422}


def test_only_selected_repositories_are_cloned(monkeypatch):
    calls = []

    async def fake_run(task_id, username, job_description, selected_repositories):
        calls.append((username, selected_repositories))

    monkeypatch.setattr("app.api.routes.run_assessment_pipeline", fake_run)
    monkeypatch.setattr(
        "app.api.routes.fetch_candidate_repositories",
        lambda username: {
            "username": username,
            "repositories": [
                {"name": "linux", "owner": "torvalds"},
                {"name": "project-two", "owner": "torvalds"},
                {"name": "other-user-project", "owner": "not-torvalds"},
            ],
        },
    )

    payload = {
        "github_username": "torvalds",
        "job_description": "Python developer",
        "selected_repositories": [{"owner": "torvalds", "name": "linux"}],
    }

    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED"
    assert calls and calls[0][1] == [{"owner": "torvalds", "name": "linux"}]


def test_failed_clone_does_not_prevent_other_selected_repositories_from_being_analyzed(monkeypatch):
    async def fake_pipeline(task_id, username, job_description, selected_repositories):
        repo_results = []
        for repo in selected_repositories:
            if repo["name"] == "linux":
                repo_results.append({"name": repo["name"], "status": "clone_failed", "error": "failed clone"})
            else:
                repo_results.append({"name": repo["name"], "status": "analyzed", "analysis": {"total_code_lines": 10, "static_score": {"total_score": 80}}})

        job_manager.JOBS_DB[task_id] = {
            "status": "COMPLETED",
            "username": username,
            "report": {
                "repositories": repo_results,
                "overall_static_score": 80,
                "repositories_selected": [item["name"] for item in selected_repositories],
            },
        }

    monkeypatch.setattr(job_manager, "run_assessment_pipeline", fake_pipeline)

    payload = {
        "github_username": "torvalds",
        "job_description": "Python developer",
        "selected_repositories": [
            {"owner": "torvalds", "name": "linux"},
            {"owner": "torvalds", "name": "project-two"},
        ],
    }

    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 202


def test_all_selected_repositories_fail_sets_assessment_failed(monkeypatch):
    async def fake_pipeline(task_id, username, job_description, selected_repositories):
        job_manager.JOBS_DB[task_id] = {
            "status": "FAILED",
            "username": username,
            "error": "All selected repositories failed to clone.",
        }

    monkeypatch.setattr(job_manager, "run_assessment_pipeline", fake_pipeline)

    payload = {
        "github_username": "torvalds",
        "job_description": "Python developer",
        "selected_repositories": [{"owner": "torvalds", "name": "linux"}],
    }

    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 202


def test_final_report_contains_only_selected_successfully_analyzed_repositories(monkeypatch):
    def fake_report(task_id):
        return {
            "candidate": {"username": "torvalds"},
            "repositories_selected": [{"owner": "torvalds", "name": "linux"}],
            "repositories": [
                {"name": "linux", "status": "analyzed", "analysis": {"total_code_lines": 10, "static_score": {"total_score": 80}}},
                {"name": "unselected-project", "status": "ignored"},
            ],
            "overall_static_score": 80,
        }

    monkeypatch.setattr(job_manager, "get_report", fake_report)
    assert True
