from app.ai_service import test_gemini
from app.question_generator import generate_questions
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
class GenerateQuestionsRequest(BaseModel):
    task_id: str
    repository: str
    selected_categories: list[str]
    job_description: Optional[str] = None
@router.get("/test-question-generator")
def test_question_generator():

    questions = generate_questions(
        repository_name="mudvault",
        languages=["Python", "JavaScript"],
        analysis={
            "files": 6,
            "lines": 317,
            "functions": 12,
            "complexity": 17,
            "code_smells": 5,
            "tests": False,
            "security_issues": 0,
        },
        selected_categories=[
            "Repository-Based",
            "Code Understanding",
            "Improvement",
        ],
        job_description=None,
    )

    return {
        "questions": questions
    }


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
@router.post("/generate-questions")
async def generate_interview_questions(request: GenerateQuestionsRequest):

    # Find the completed analysis job
    job = JOBS_DB.get(request.task_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Task ID not found"
        )

    if job["status"] != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Repository analysis is not completed yet."
        )

    report = job.get("report")

    if not report:
        raise HTTPException(
            status_code=400,
            detail="Assessment report is not available."
        )

    # Find the requested repository
    repository_result = next(
        (
            repo
            for repo in report.get("repositories", [])
            if repo.get("name") == request.repository
        ),
        None
    )

    if not repository_result:
        raise HTTPException(
            status_code=404,
            detail="Repository not found in this assessment."
        )

    analysis = repository_result.get("analysis")

    analysis = repository_result.get("analysis")

    if not analysis:
        raise HTTPException(
            status_code=400,
            detail="No static analysis available for this repository."
        )

    languages = repository_result.get("languages", [])

    # Generate questions using Gemini
    questions = generate_questions(
        repository_name=request.repository,
        languages=languages,
        analysis=analysis,
        selected_categories=request.selected_categories,
        job_description=request.job_description,
    )

    return questions