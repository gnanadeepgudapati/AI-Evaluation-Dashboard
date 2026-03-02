# dashboard_server.py
# This is the entry point for the entire backend.
# Run this file to start the API server.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.evaluation_routes import router

app = FastAPI(
    title="AI Evaluation Dashboard",
    description="Evaluates AI agent responses across four metrics — groundedness, relevance, safety, and completeness.",
    version="1.0.0"
)

# CORS — allows the frontend to talk to the backend
# In production you'd lock this down to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Register all the evaluation routes
app.include_router(router)


@app.get("/")
def health_check():
    return {"status": "AI Evaluation Dashboard is running"}