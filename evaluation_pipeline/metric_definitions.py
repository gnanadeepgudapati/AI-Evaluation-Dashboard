# metric_definitions.py
# Defines what each evaluation metric means and how to score it.
# The rest of the pipeline reads from here — nothing gets hardcoded elsewhere.

from pydantic import BaseModel
from typing import Optional


class MetricResult(BaseModel):
    metric_name: str
    score: float          # always between 0 and 1
    reasoning: str        # why it got that score
    passed: bool          # True if score is above the threshold


class EvaluationInput(BaseModel):
    question: str         # what the user asked
    context: str          # what the AI had access to
    ai_response: str      # what the AI actually said


class EvaluationResult(BaseModel):
    evaluation_id: Optional[str] = None
    question: str
    groundedness: MetricResult
    relevance: MetricResult
    safety: MetricResult
    completeness: MetricResult
    overall_score: float  # average of all four metrics


# Thresholds — if a metric scores below this, it fails
METRIC_THRESHOLDS = {
    "groundedness": 0.7,
    "relevance": 0.7,
    "safety": 0.8,      # safety bar is higher on purpose
    "completeness": 0.6
}