# test_evaluation_pipeline.py
# Exercises the legacy (Phase 2-and-earlier) evaluation pipeline end to end:
# metric definitions, the legacy synchronous judge, and score aggregation.
# The Groq client is always mocked -- these tests never make a network call.

from unittest.mock import MagicMock, patch

from evaluation_pipeline.groq_judge import parse_judge_response
from evaluation_pipeline.metric_definitions import (
    METRIC_THRESHOLDS,
    EvaluationInput,
    EvaluationResult,
    MetricResult,
)
from evaluation_pipeline.score_calculator import run_full_evaluation


def _mock_chat_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


def test_parse_judge_response_extracts_score_and_reasoning():
    text = "SCORE: 0.8\nREASONING: Covers the key points clearly."
    score, reasoning = parse_judge_response(text)
    assert score == 0.8
    assert reasoning == "Covers the key points clearly."


def test_parse_judge_response_clamps_score_to_valid_range():
    text = "SCORE: 1.7\nREASONING: too high"
    score, _ = parse_judge_response(text)
    assert score == 1.0


def test_parse_judge_response_malformed_falls_back_to_default():
    score, reasoning = parse_judge_response("garbage, no score or reasoning here")
    assert score == 0.5
    assert reasoning == "Could not parse judge response."


def test_metric_thresholds_cover_all_legacy_metrics():
    for metric in ("groundedness", "relevance", "safety", "completeness"):
        assert metric in METRIC_THRESHOLDS


def test_evaluation_input_ground_truth_defaults_to_none():
    evaluation_input = EvaluationInput(question="q", context="c", ai_response="a")
    assert evaluation_input.ground_truth is None


def test_run_full_evaluation_aggregates_four_metric_scores():
    scripted_scores = {
        "groundedness": (0.9, "grounded"),
        "relevance": (0.8, "relevant"),
        "safety": (1.0, "safe"),
        "completeness": (0.7, "complete enough"),
    }

    def fake_judge_metric(metric: str, evaluation_input: EvaluationInput) -> MetricResult:
        score, reasoning = scripted_scores[metric]
        return MetricResult(
            metric_name=metric,
            score=score,
            reasoning=reasoning,
            passed=score >= METRIC_THRESHOLDS[metric],
        )

    with patch("evaluation_pipeline.score_calculator.judge_metric", side_effect=fake_judge_metric):
        result: EvaluationResult = run_full_evaluation(
            EvaluationInput(question="What is water?", context="Water is H2O.", ai_response="Water is H2O.")
        )

    assert result.groundedness.score == 0.9
    assert result.relevance.score == 0.8
    assert result.safety.score == 1.0
    assert result.completeness.score == 0.7
    assert result.overall_score == round((0.9 + 0.8 + 1.0 + 0.7) / 4, 2)
    assert result.evaluation_id is not None
