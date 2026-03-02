# evaluation_routes.py
# All the API endpoints live here.
# dashboard_server.py plugs this in automatically.

from fastapi import APIRouter, HTTPException
from evaluation_pipeline.metric_definitions import EvaluationInput, EvaluationResult
from evaluation_pipeline.score_calculator import run_full_evaluation

router = APIRouter()

# In-memory storage for Phase 1 — Phase 2 replaces this with SQLite
evaluation_history = []


@router.post("/evaluate", response_model=EvaluationResult)
def evaluate_response(input: EvaluationInput):
    """
    Submit an AI response for evaluation.
    Send a question, context, and AI response — get back scores for all four metrics.
    """
    try:
        result = run_full_evaluation(input)
        evaluation_history.append(result.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluations")
def get_all_evaluations():
    """
    Get every evaluation that's been run this session.
    """
    if not evaluation_history:
        return {"message": "No evaluations run yet.", "evaluations": []}
    return {"total": len(evaluation_history), "evaluations": evaluation_history}


@router.get("/evaluations/{evaluation_id}")
def get_single_evaluation(evaluation_id: str):
    """
    Get one specific evaluation by its ID.
    """
    for evaluation in evaluation_history:
        if evaluation["evaluation_id"] == evaluation_id:
            return evaluation
    raise HTTPException(status_code=404, detail="Evaluation not found.")