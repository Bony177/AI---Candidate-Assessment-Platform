from app.ai_service import test_gemini
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from typing import Optional
import uuid


from app.services.job_manager import JOBS_DB, run_assessment_pipeline, _select_repositories
from app.services.github_service import fetch_github_data

router = APIRouter()

class AnalyzeRequest(BaseModel):
    github_username: str
    selected_repositories: list[str]
    job_description: Optional[str] = None


@router.get("/test-gemini")
def test_gemini_endpoint():
    return {
        "message": test_gemini()
    }
@router.get("/repositories/{username}")
async def get_repositories(username: str):
    try:
        raw_github = await fetch_github_data(username)

        repositories = _select_repositories(raw_github)

        # Contribution data
        contribution_calendar = (
            raw_github.get("contributionsCollection", {})
            .get("contributionCalendar", {})
        )

        total_contributions = contribution_calendar.get(
            "totalContributions", 0
        )

        contribution_days = []

        for week in contribution_calendar.get("weeks", []):
            for day in week.get("contributionDays", []):
                contribution_days.append(day)

        active_days = sum(
            1
            for day in contribution_days
            if day.get("contributionCount", 0) > 0
        )

        # Repository data
        formatted_repositories = []

        for repository in repositories:
            formatted_repositories.append({
                "name": repository.get("name"),
                "description": repository.get("description"),
                "url": repository.get("url"),

                "primary_language": (
                    repository.get("primaryLanguage", {}) or {}
                ).get("name"),

                "languages": [
                    edge.get("node", {}).get("name")
                    for edge in (
                        repository.get("languages", {}).get("edges", [])
                        or []
                    )
                    if edge.get("node")
                ],

                "stars": repository.get("stargazerCount", 0),
                "forks": repository.get("forkCount", 0),
            })

        return {
            "candidate": {
                "username": raw_github.get("login"),
                "name": raw_github.get("name"),
                "avatar_url": raw_github.get("avatarUrl"),
                "bio": raw_github.get("bio"),
                "followers": (
                    raw_github.get("followers", {})
                    .get("totalCount", 0)
                ),
                "total_contributions": total_contributions,
                "active_days": active_days,
            },

            "repositories": formatted_repositories,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch repositories: {str(error)}",
        )

@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    
    # Initialize the record in our tracker
    JOBS_DB[task_id] = {
        "status": "QUEUED",
        "username": request.github_username,
        "report": None,
        "error": None
    }

    # Dispatch background task without blocking the HTTP response
    background_tasks.add_task(
    run_assessment_pipeline, 
    task_id, 
    request.github_username, 
    request.job_description,
    request.selected_repositories,
     )

    return {
        "task_id": task_id,
        "status": "QUEUED",
        "message": "Candidate analysis started in the background."
    }

@router.get("/status/{task_id}")
async def get_analysis_status(task_id: str):
    job = JOBS_DB.get(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Task ID not found")
    
    return {
        "task_id": task_id,
        "status": job["status"],
        "error": job.get("error")
    }

@router.get("/report/{task_id}")
async def get_analysis_report(task_id: str):
    job = JOBS_DB.get(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Task ID not found")
    
    if job["status"] != "COMPLETED":
        raise HTTPException(
            status_code=400, 
            detail=f"Report is not ready yet. Current status: {job['status']}"
        )
    
    return job["report"]
