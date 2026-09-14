from app.ai_service import client
import json


QUESTION_CATEGORIES = [
    "Repository-Based",
    "Code Understanding",
    "Technical Concepts",
    "Problem Solving",
    "Improvement",
    "Job Role",
]


def generate_questions(
    repository_name: str,
    languages: list[str],
    analysis: dict,
    selected_categories: list[str],
    job_description: str | None = None,
):
    
    prompt = f"""
You are a technical interviewer evaluating a software developer.

Generate interview questions specifically based on the candidate's repository
and the static analysis results provided below.

IMPORTANT RULES:
- Do not invent technologies, features, or implementation details.
- Questions must be grounded in the provided repository information.
- Generate exactly 3 questions for each selected category.
- Make questions practical and suitable for a technical interview.
- Avoid duplicate or very similar questions.
- Return ONLY valid JSON.

REPOSITORY:
Name: {repository_name}

LANGUAGES:
{languages}

STATIC ANALYSIS:
{analysis}

SELECTED QUESTION CATEGORIES:
{selected_categories}

JOB DESCRIPTION:
{job_description or "Not provided"}

Return this exact JSON structure:

{{
    "repository": "{repository_name}",
    "questions": [
        {{
            "category": "Repository-Based",
            "question": "Question here",
            "reason": "Why this question is relevant to the repository"
        }}
    ]
}}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
    )

    return json.loads(response.text)