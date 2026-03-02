"""
All evaluation-related API endpoints.

Routes:
    POST /evaluate          — run all four scorers and persist the result
    GET  /history           — paginated list of past evaluations
    GET  /history/{id}      — single evaluation by id
    GET  /metrics/averages  — aggregate average scores across all evaluations
"""

from fastapi import APIRouter, HTTPException, Query

from database.evaluation_store import (
    get_all_evaluations,
    get_evaluation_by_id,
    get_metric_averages,
    save_evaluation,
)
from evaluation_pipeline.metric_definitions import EvaluationRequest, EvaluationResult
from evaluation_pipeline.score_calculator import evaluate

router = APIRouter(prefix="/api", tags=["evaluation"])


@router.post("/evaluate", response_model=EvaluationResult, status_code=201)
def run_evaluation(request: EvaluationRequest) -> EvaluationResult:
    """
    Evaluate an AI agent response across all four metrics and persist the result.

    - **question**: The user's question or prompt.
    - **response**: The AI agent's answer to evaluate.
    - **context**: Optional reference text used for groundedness scoring.
    """
    result = evaluate(request)
    save_evaluation(result.model_dump())
    return result


@router.get("/history", summary="List evaluation history")
def list_history(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum rows to return"),
    offset: int = Query(default=0, ge=0, description="Rows to skip for pagination"),
) -> list[dict]:
    """Return a paginated list of past evaluation results, most-recent first."""
    return get_all_evaluations(limit=limit, offset=offset)


@router.get("/history/{evaluation_id}", summary="Get single evaluation")
def get_history_item(evaluation_id: int) -> dict:
    """Return the full record for a single evaluation by its id."""
    record = get_evaluation_by_id(evaluation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return record


@router.get("/metrics/averages", summary="Metric averages")
def metric_averages() -> dict:
    """Return the average score for each metric across all stored evaluations."""
    return get_metric_averages()
