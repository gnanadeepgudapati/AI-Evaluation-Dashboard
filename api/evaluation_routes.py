# evaluation_routes.py
# All API endpoints live here.
# dashboard_server.py plugs this in automatically.

from fastapi import APIRouter, HTTPException
from evaluation_pipeline.metric_definitions import EvaluationInput, EvaluationResult
from evaluation_pipeline.score_calculator import run_full_evaluation
from database.evaluation_store import save_evaluation, get_all_evaluations, get_evaluation_by_id

router = APIRouter()


@router.post("/evaluate", response_model=EvaluationResult)
def evaluate_response(input: EvaluationInput):
    """
    Submit an AI response for evaluation.
    Returns scores for all four metrics with reasoning.
    """
    try:
        result = run_full_evaluation(input)
        save_evaluation(result.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluations")
def get_all():
    """
    Get every evaluation stored in the database, newest first.
    """
    evaluations = get_all_evaluations()
    if not evaluations:
        return {"message": "No evaluations yet.", "evaluations": []}
    return {"total": len(evaluations), "evaluations": evaluations}


@router.get("/evaluations/{evaluation_id}")
def get_one(evaluation_id: str):
    """
    Get one specific evaluation by its ID.
    """
    evaluation = get_evaluation_by_id(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return evaluation