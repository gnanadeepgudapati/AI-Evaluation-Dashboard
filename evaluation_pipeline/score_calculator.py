# score_calculator.py
# Runs all four metric scorers and aggregates the results.
# Phase 1 had hardcoded placeholder scores — this is the real thing.

from evaluation_pipeline.metric_definitions import (
    EvaluationInput,
    EvaluationResult
)
from evaluation_pipeline.groq_judge import judge_metric
import uuid


def run_full_evaluation(input: EvaluationInput) -> EvaluationResult:
    
    print(f"Running evaluation for question: {input.question[:50]}...")
    
    # Send each metric to the Groq judge separately
    groundedness  = judge_metric("groundedness", input)
    relevance     = judge_metric("relevance", input)
    safety        = judge_metric("safety", input)
    completeness  = judge_metric("completeness", input)

    # Overall score is the average of all four
    overall = round(
        (groundedness.score + relevance.score + 
         safety.score + completeness.score) / 4, 2
    )

    print(f"Evaluation complete. Overall score: {overall}")

    return EvaluationResult(
        evaluation_id=str(uuid.uuid4()),
        question=input.question,
        groundedness=groundedness,
        relevance=relevance,
        safety=safety,
        completeness=completeness,
        overall_score=overall
    )