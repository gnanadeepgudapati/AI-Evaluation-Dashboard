"""
FastAPI application entry point for the AI Evaluation Dashboard.

Run with:
    uvicorn api.dashboard_server:app --reload --host 0.0.0.0 --port 8000
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.evaluation_routes import router as evaluation_router

load_dotenv()

app = FastAPI(
    title="AI Evaluation Dashboard",
    description=(
        "An LLM-as-judge evaluation pipeline that scores AI agent responses "
        "on groundedness, relevance, safety, and completeness."
    ),
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS — allow all origins in development; tighten in production
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(evaluation_router)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    """Simple health-check endpoint."""
    return {"status": "ok", "version": app.version}


# ---------------------------------------------------------------------------
# Static frontend files — mounted last so API routes take priority
# ---------------------------------------------------------------------------
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
