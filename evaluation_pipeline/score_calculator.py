# score_calculator.py
# Computes scores for each metric. 
# Phase 1 — placeholder logic. Phase 2 replaces these with real Groq API calls.

from evaluation_pipeline.metric_definitions import (
    EvaluationInput,
    EvaluationResult,
    MetricResult,
    METRIC_THRESHOLDS
)
import uuid


def score_groundedness(input: EvaluationInput) -> MetricResult:
    # Placeholder — Phase 2 will send this to Groq for real scoring
    score = 0.75
    threshold = METRIC_THRESHOLDS["groundedness"]
    return MetricResult(
        metric_name="groundedness",
        score=score,
        reasoning="Placeholder score — Groq judge not connected yet.",
        passed=score >= threshold
    )


def score_relevance(input: EvaluationInput) -> MetricResult:
    score = 0.80
    threshold = METRIC_THRESHOLDS["relevance"]
    return MetricResult(
        metric_name="relevance",
        score=score,
        reasoning="Placeholder score — Groq judge not connected yet.",
        passed=score >= threshold
    )


def score_safety(input: EvaluationInput) -> MetricResult:
    score = 0.90
    threshold = METRIC_THRESHOLDS["safety"]
    return MetricResult(
        metric_name="safety",
        score=score,
        reasoning="Placeholder score — Groq judge not connected yet.",
        passed=score >= threshold
    )


def score_completeness(input: EvaluationInput) -> MetricResult:
    score = 0.65
    threshold = METRIC_THRESHOLDS["completeness"]
    return MetricResult(
        metric_name="completeness",
        score=score,
        reasoning="Placeholder score — Groq judge not connected yet.",
        passed=score >= threshold
    )


def run_full_evaluation(input: EvaluationInput) -> EvaluationResult:
    groundedness = score_groundedness(input)
    relevance = score_relevance(input)
    safety = score_safety(input)
    completeness = score_completeness(input)

    # Overall score is just the average of all four
    overall = round(
        (groundedness.score + relevance.score + safety.score + completeness.score) / 4, 2
    )

    return EvaluationResult(
        evaluation_id=str(uuid.uuid4()),
        question=input.question,
        groundedness=groundedness,
        relevance=relevance,
        safety=safety,
        completeness=completeness,
        overall_score=overall
    )