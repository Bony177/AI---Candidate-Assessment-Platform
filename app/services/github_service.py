import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GRAPHQL_URL = "https://api.github.com/graphql"

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
        response = await client.post(
            GRAPHQL_URL,
            json={"query": GRAPHQL_QUERY, "variables": {"username": username}},
            headers=headers,
            timeout=20.0
        )
        
        if response.status_code != 200:
            raise Exception(f"GitHub API Error: {response.status_code} - {response.text}")

        data = response.json()
        if "errors" in data:
            raise Exception(f"GraphQL Query Error: {data['errors']}")

        user = data.get("data", {}).get("user")
        if not user:
            raise ValueError(f"User '{username}' not found on GitHub.")

        return user

