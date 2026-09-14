import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set")

client = genai.Client(api_key=api_key)


def test_gemini():
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Say hello in one short sentence."
    )

    return response.text