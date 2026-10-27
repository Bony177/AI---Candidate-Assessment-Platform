import asyncio
import os
from pathlib import Path
import logging

import httpx
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GRAPHQL_URL = "https://api.github.com/graphql"
MAX_RETRIES = 2
RETRY_BASE_SECONDS = 0.25
RETRYABLE_STATUS_CODES = {502, 503, 504}
logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code

GRAPHQL_QUERY = """
query($username: String!) {
  user(login: $username) {
    name
    login
    avatarUrl
    bio
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    repositories(first: 100, orderBy: {field: PUSHED_AT, direction: DESC}, isFork: false, privacy: PUBLIC) {
      nodes {
  name
  description
  url

  owner {
    login
  }

  isFork
  isArchived

  stargazerCount
  forkCount

  primaryLanguage {
    name
  }

  languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: 30) {
                totalCount
                nodes {
                  message
                  committedDate
                  additions
                  deletions
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

async def fetch_github_data(username: str) -> dict:
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN is missing in environment variables.")

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.post(
                    GRAPHQL_URL,
                    json={
                        "query": GRAPHQL_QUERY,
                        "variables": {"username": username},
                    },
                    headers=headers,
                    timeout=20.0,
                )
            except httpx.TransportError as error:
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_SECONDS * (2**attempt)
                    logger.warning(
                        "GitHub request failed (%s); retrying in %.2fs",
                        type(error).__name__,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise GitHubAPIError(
                    502,
                    "GitHub could not be reached. Please try again shortly.",
                ) from error

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_SECONDS * (2**attempt)
                    logger.warning(
                        "GitHub returned HTTP %s; retrying in %.2fs",
                        response.status_code,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise GitHubAPIError(
                    502,
                    (
                        "GitHub is temporarily unavailable "
                        f"(HTTP {response.status_code}). Please try again shortly."
                    ),
                )

            if response.status_code != 200:
                logger.warning(
                    "GitHub API returned HTTP %s",
                    response.status_code,
                )
                raise GitHubAPIError(
                    502,
                    (
                        "GitHub rejected the repository request "
                        f"(HTTP {response.status_code}). Check the server's "
                        "GitHub token and API rate limit."
                    ),
                )

            try:
                data = response.json()
            except ValueError as error:
                raise GitHubAPIError(
                    502,
                    "GitHub returned an invalid response. Please try again shortly.",
                ) from error

            if "errors" in data:
                logger.warning("GitHub GraphQL request returned errors")
                raise GitHubAPIError(
                    502,
                    "GitHub could not complete the repository query.",
                )

            user = data.get("data", {}).get("user")
            if not user:
                raise ValueError(f"User '{username}' not found on GitHub.")

            return user
