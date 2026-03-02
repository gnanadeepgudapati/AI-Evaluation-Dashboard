"""
Handles all communication with the Groq API for LLM-as-judge scoring.

Phase 1: stub only — no actual API calls are made.
Phase 2: implement judge_metric() to call the Groq chat completions endpoint
         and parse structured scores from the model response.
"""

import os
from typing import Any

from evaluation_pipeline.metric_definitions import EvaluationRequest


GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-8b-8192")
GROQ_API_BASE: str = "https://api.groq.com/openai/v1"


def is_configured() -> bool:
    """Return True if a Groq API key is available in the environment."""
    return bool(GROQ_API_KEY)


async def judge_metric(
    request: EvaluationRequest,
    metric: str,
    criteria: str,
) -> dict[str, Any]:
    """
    [Phase 2 stub] Call the Groq API to score a single metric.

    Args:
        request: The evaluation request containing question, response, and context.
        metric:  Name of the metric being scored (e.g. "groundedness").
        criteria: Scoring rubric text describing how to assign the score.

    Returns:
        A dict with keys: "score" (float 0–1), "level" (str), "reasoning" (str).

    Raises:
        NotImplementedError: until Phase 2 is implemented.
    """
    raise NotImplementedError(
        "Groq integration is planned for Phase 2. "
        "Use evaluation_pipeline.score_calculator.evaluate() for Phase 1 scoring."
    )
