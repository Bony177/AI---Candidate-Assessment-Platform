import uuid
import asyncio
import logging
from typing import Dict, Any

from app.services.github_service import fetch_github_data
from app.services.repo_cloner import clone_repositories, cleanup_cloned_repos
from app.services.analyzer import analyze_repository

logger = logging.getLogger(__name__)

MAX_REPOSITORIES = 3

# In-memory store for task states
# In production, replace with Redis or Postgres
JOBS_DB: Dict[str, Dict[str, Any]] = {}


def _select_repositories(raw_github: dict) -> list[dict]:
    """Select public, non-fork, non-archived repositories owned by the candidate."""

    selected = []

    repositories = raw_github.get("repositories", {}).get("nodes", [])
    candidate_login = raw_github.get("login", "").lower()

    for repository in repositories:
        if not repository:
            continue

        # Skip forked repositories
        if repository.get("isFork"):
            continue

        # Skip archived repositories
        if repository.get("isArchived"):
            continue

        owner = repository.get("owner") or {}
        owner_login = owner.get("login", "").lower()

        # Safety check: repository must belong to the candidate
        if owner_login != candidate_login:
            logger.warning(
                "Skipping repository %s because owner is %s, expected %s",
                repository.get("name"),
                owner_login,
                candidate_login,
            )
            continue

        selected.append(repository)

    return selected


def _calculate_overall_score(repository_results: list[dict]) -> int | None:
    """Weight analyzable repository scores by their Python code-line counts."""

    weighted_score = 0.0
    total_lines = 0

    for result in repository_results:
        analysis = result.get("analysis")

        if result.get("status") != "analyzed" or not analysis:
            continue

        code_lines = analysis.get("total_code_lines", 0)
        score = analysis.get("static_score", {}).get("total_score")

        if score is None:
            continue

        weight = code_lines or 1
        weighted_score += score * weight
        total_lines += weight

    if not total_lines:
        return None

    return round(weighted_score / total_lines)


async def run_assessment_pipeline(
    task_id: str,
    username: str,
    job_description: str | None,
    selected_repository_names: list[str],
):
    cloned_paths = {}

    try:
        logger.info("Starting candidate analysis for %s", username)

        # ---------------------------------------------------------
        # Stage 1: Fetch GitHub metadata
        # ---------------------------------------------------------
        JOBS_DB[task_id]["status"] = "FETCHING_GITHUB_METADATA"

        raw_github = await fetch_github_data(username)

        # Get all eligible repositories
        eligible_repositories = _select_repositories(raw_github)

        # Convert selected repository names into a set
        selected_names = set(selected_repository_names)

        # Keep ONLY repositories selected by the interviewer
        selected_repositories = [
            repository
            for repository in eligible_repositories
            if repository.get("name") in selected_names
        ]

        # Make sure at least one repository was selected
        if not selected_repositories:
            raise ValueError("No valid repositories were selected.")

        # Enforce maximum repository selection
        if len(selected_repositories) > MAX_REPOSITORIES:
            raise ValueError(
                f"You can select a maximum of {MAX_REPOSITORIES} repositories."
            )

        repo_names = [
            repository["name"]
            for repository in selected_repositories
        ]

        logger.info(
            "Selected repositories for %s: %s",
            username,
            repo_names,
        )

        # ---------------------------------------------------------
        # Stage 2: Clone ONLY selected repositories
        # ---------------------------------------------------------
        JOBS_DB[task_id]["status"] = "CLONING_REPOSITORIES"

        cloned_paths = await asyncio.to_thread(
            clone_repositories,
            selected_repositories,
            max_repos=MAX_REPOSITORIES,
        )

        # ---------------------------------------------------------
        # Stage 3: Static analysis
        # ---------------------------------------------------------
        JOBS_DB[task_id]["status"] = "RUNNING_STATIC_ANALYSIS"

        repository_results = []

        for repository in selected_repositories:
            name = repository["name"]

            repository_result = {
                "name": name,
                "url": (
                    repository.get("url")
                    or f"https://github.com/{username}/{name}"
                ),
            }

            clone_path = cloned_paths.get(name)

            # Clone failed
            if not clone_path:
                repository_result.update({
                    "status": "clone_failed",
                    "error": "Repository could not be cloned.",
                })

                repository_results.append(repository_result)

                logger.warning(
                    "Skipping %s because cloning failed",
                    name,
                )

                continue

            try:
                logger.info(
                    "Starting static analysis for %s at %s",
                    name,
                    clone_path,
                )

                analysis = await asyncio.to_thread(
                    analyze_repository,
                    clone_path,
                )

                # Repository does not contain supported Python files
                if not analysis.get("files_analyzed"):
                    repository_result.update({
                        "status": "unsupported_for_static_analysis",
                        "analysis": analysis,
                        "static_score": None,
                    })

                    logger.info(
                        "Repository %s has no Python files",
                        name,
                    )

                # Repository successfully analyzed
                else:
                    repository_result.update({
                        "status": "analyzed",
                        "analysis": analysis,
                        "static_score": analysis["static_score"],
                    })

                    logger.info(
                        "Completed static analysis for %s with score %s",
                        name,
                        analysis["static_score"]["total_score"],
                    )

            except Exception as error:
                repository_result.update({
                    "status": "analysis_failed",
                    "error": str(error),
                })

                logger.exception(
                    "Static analysis failed for %s",
                    name,
                )

            repository_results.append(repository_result)

        # ---------------------------------------------------------
        # Calculate overall static score
        # ---------------------------------------------------------
        overall_static_score = _calculate_overall_score(
            repository_results
        )

        logger.info(
            "Overall static score for %s: %s",
            username,
            overall_static_score,
        )

        # ---------------------------------------------------------
        # Stage 4: AI Matching Hook
        # ---------------------------------------------------------
        JOBS_DB[task_id]["status"] = "RUNNING_AI_EVALUATION"

        await asyncio.sleep(2)

        mock_ai_results = {
            "jd_match_percentage": 82,
            "matched_skills": [
                "JavaScript",
                "HTML",
            ],
            "interview_questions": [
                (
                    f"In your repository "
                    f"'{repo_names[0] if repo_names else 'project'}', "
                    "how did you organize your frontend assets "
                    "and state management?"
                )
            ],
        }

        # ---------------------------------------------------------
        # Stage 5: Final report
        # ---------------------------------------------------------
        JOBS_DB[task_id]["status"] = "COMPLETED"

        JOBS_DB[task_id]["report"] = {
            "candidate": {
                "username": raw_github.get("login"),
                "avatar_url": raw_github.get("avatarUrl"),
                "total_contributions": (
                    raw_github[
                        "contributionsCollection"
                    ][
                        "contributionCalendar"
                    ][
                        "totalContributions"
                    ]
                ),
            },

            "repositories_analyzed": sum(
                result.get("status") == "analyzed"
                for result in repository_results
            ),

            "repositories": repository_results,

            "overall_static_score": overall_static_score,

            "jd_match_and_interview": mock_ai_results,
        }

    except Exception as error:
        JOBS_DB[task_id]["status"] = "FAILED"
        JOBS_DB[task_id]["error"] = str(error)

        logger.exception(
            "Candidate analysis failed for %s",
            username,
        )

    finally:
        # Always clean up cloned repositories
        if cloned_paths:
            cleanup_cloned_repos(cloned_paths)

            logger.info(
                "Cleaned up cloned repositories for %s",
                username,
            )