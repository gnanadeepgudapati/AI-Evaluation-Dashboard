# dashboard_server.py
# Entry point for the entire backend.
# Run this file to start the API server.

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.compare_routes import router as compare_router
from api.evaluation_routes import router
from database.arena_store import initialize_arena_db
from database.evaluation_store import initialize_database

# Initialize the legacy database when the server starts
initialize_database()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await initialize_arena_db()
    yield


app = FastAPI(
    title="AI Evaluation Dashboard",
    description="Evaluates AI agent responses across four metrics — groundedness, relevance, safety, and completeness.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allows the frontend to talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Serve the frontend files statically
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Register all the evaluation routes
app.include_router(router)
app.include_router(compare_router)


@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("frontend/index.html")

@app.get("/")
def health_check():
    return {"status": "AI Evaluation Dashboard is running"}