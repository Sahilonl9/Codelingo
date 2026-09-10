"""
CodeLingo backend — FastAPI app.

Two small endpoints power the whole product:
  POST /api/explain  {code}                -> line-by-line plain-English translation
  POST /api/check    {expected, submitted} -> how close the learner's typed code is

Everything else (samples, static frontend) is just convenience plumbing.
Run with: uvicorn main:app --reload --port 8000
"""

import re
from difflib import SequenceMatcher
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from explainer import explain_code

app = FastAPI(title="CodeLingo")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class ExplainRequest(BaseModel):
    code: str


class CheckRequest(BaseModel):
    expected: str
    submitted: str


SAMPLES = {
    "django_search": {
        "title": "Django: search a model with OR logic",
        "code": """from django.db.models import Q
from django.shortcuts import render
from .models import Article  # Replace with your actual model

def search_articles(request):
    # Get the search query from the URL parameter (e.g., /search/?q=python)
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        # Search for the token across title or content fields
        results = Article.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        ).distinct()

    return render(request, 'search_results.html', {
        'query': query,
        'results': results
    })
""",
    },
    "list_comprehension": {
        "title": "Python: filter + transform a list",
        "code": """def even_squares(numbers):
    # Keep only even numbers, then square each one
    squares = [n * n for n in numbers if n % 2 == 0]
    return squares
""",
    },
}


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


@app.post("/api/explain")
def api_explain(req: ExplainRequest):
    return {"lines": explain_code(req.code)}


@app.get("/api/samples")
def api_samples():
    return SAMPLES


@app.post("/api/check")
def api_check(req: CheckRequest):
    a, b = _normalize(req.expected), _normalize(req.submitted)
    ratio = SequenceMatcher(None, a, b).ratio() if a and b else 0.0
    correct = ratio >= 0.72 and bool(b.strip())

    if not b.strip():
        hint = "Give it a try — even a rough guess helps you learn the shape of the line."
    elif correct:
        hint = "Nailed it."
    elif ratio >= 0.5:
        hint = "Close! Check the exact method names, quotes, and punctuation."
    else:
        hint = "Not quite yet — re-read the English line above and try to match its structure piece by piece."

    return {"ratio": round(ratio, 2), "correct": correct, "hint": hint}


# Serve the frontend last so /api/* routes above take priority.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
