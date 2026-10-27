import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.services import github_service
from app.services.github_service import GitHubAPIError


client = TestClient(app)


def _github_response(status_code, payload=None):
    return SimpleNamespace(
        status_code=status_code,
        json=lambda: payload,
    )


def test_github_502_retries_and_succeeds(monkeypatch):
    responses = [
        _github_response(502),
        _github_response(200, {"data": {"user": {"login": "ashlin311"}}}),
    ]
    delays = []

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return responses.pop(0)

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(github_service, "GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(github_service.httpx, "AsyncClient", MockAsyncClient)
    monkeypatch.setattr(github_service.asyncio, "sleep", record_sleep)

    user = asyncio.run(github_service.fetch_github_data("ashlin311"))

    assert user == {"login": "ashlin311"}
    assert responses == []
    assert delays == [github_service.RETRY_BASE_SECONDS]


def test_persistent_github_502_returns_sanitized_gateway_error(monkeypatch):
    calls = []
    delays = []

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            calls.append(True)
            return _github_response(502)

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(github_service, "GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(github_service.httpx, "AsyncClient", MockAsyncClient)
    monkeypatch.setattr(github_service.asyncio, "sleep", record_sleep)

    with pytest.raises(GitHubAPIError) as error:
        asyncio.run(github_service.fetch_github_data("ashlin311"))

    assert error.value.status_code == 502
    assert "temporarily unavailable" in str(error.value)
    assert "nginx" not in str(error.value).lower()
    assert len(calls) == github_service.MAX_RETRIES + 1
    assert len(delays) == github_service.MAX_RETRIES


def test_repository_endpoint_returns_sanitized_502(monkeypatch):
    async def fail_upstream(_username):
        raise GitHubAPIError(502, "GitHub is temporarily unavailable.")

    monkeypatch.setattr(routes, "fetch_github_data", fail_upstream)

    response = client.get("/api/v1/repositories/ashlin311")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "GitHub is temporarily unavailable."
    }
