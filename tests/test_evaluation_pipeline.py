"""
Tests for Phase 1 of the evaluation pipeline.

Covers:
- Pydantic model validation for all four metric types
- Placeholder scorer functions (score_groundedness, score_relevance,
  score_safety, score_completeness)
- compute_overall_score aggregation
- Full evaluate() integration
- FastAPI endpoints via TestClient
"""

import pytest
from fastapi.testclient import TestClient

from evaluation_pipeline.metric_definitions import (
    CompletenessScore,
    EvaluationRequest,
    EvaluationResult,
    GroundednessScore,
    RelevanceScore,
    SafetyScore,
    ScoreLevel,
)
from evaluation_pipeline.score_calculator import (
    METRIC_WEIGHTS,
    compute_overall_score,
    evaluate,
    score_completeness,
    score_groundedness,
    score_relevance,
    score_safety,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_request(question="What is AI?", response="AI is artificial intelligence.",
                 context="") -> EvaluationRequest:
    return EvaluationRequest(question=question, response=response, context=context)


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------

class TestMetricModels:
    def test_groundedness_valid(self):
        s = GroundednessScore(score=0.8, level=ScoreLevel.HIGH, reasoning="ok")
        assert s.score == 0.8
        assert s.level == ScoreLevel.HIGH

    def test_groundedness_score_bounds(self):
        with pytest.raises(Exception):
            GroundednessScore(score=1.5, level=ScoreLevel.HIGH)
        with pytest.raises(Exception):
            GroundednessScore(score=-0.1, level=ScoreLevel.LOW)

    def test_relevance_valid(self):
        s = RelevanceScore(score=0.5, level=ScoreLevel.MEDIUM)
        assert s.score == 0.5

    def test_safety_valid(self):
        s = SafetyScore(score=1.0, level=ScoreLevel.HIGH)
        assert s.level == ScoreLevel.HIGH

    def test_completeness_valid(self):
        s = CompletenessScore(score=0.0, level=ScoreLevel.LOW)
        assert s.score == 0.0

    def test_evaluation_request_requires_question(self):
        with pytest.raises(Exception):
            EvaluationRequest(question="", response="some response")

    def test_evaluation_request_requires_response(self):
        with pytest.raises(Exception):
            EvaluationRequest(question="What?", response="")

    def test_evaluation_request_context_defaults_empty(self):
        req = EvaluationRequest(question="Q?", response="A.")
        assert req.context == ""


# ---------------------------------------------------------------------------
# score_groundedness
# ---------------------------------------------------------------------------

class TestScoreGroundedness:
    def test_no_context_returns_neutral(self):
        req = make_request(context="")
        result = score_groundedness(req)
        assert result.score == 0.5
        assert result.level == ScoreLevel.MEDIUM

    def test_perfect_overlap(self):
        req = make_request(
            context="the quick brown fox",
            response="the quick brown fox jumped",
        )
        result = score_groundedness(req)
        assert result.score == 1.0
        assert result.level == ScoreLevel.HIGH

    def test_no_overlap(self):
        req = make_request(context="apple banana cherry", response="dog cat fish")
        result = score_groundedness(req)
        assert result.score == 0.0
        assert result.level == ScoreLevel.LOW

    def test_partial_overlap(self):
        req = make_request(context="alpha beta gamma delta", response="alpha beta")
        result = score_groundedness(req)
        assert 0.0 < result.score < 1.0

    def test_score_in_bounds(self):
        req = make_request(context="x y z", response="a b c d e f")
        result = score_groundedness(req)
        assert 0.0 <= result.score <= 1.0


# ---------------------------------------------------------------------------
# score_relevance
# ---------------------------------------------------------------------------

class TestScoreRelevance:
    def test_high_overlap(self):
        req = make_request(question="what is machine learning",
                           response="machine learning is what we use")
        result = score_relevance(req)
        assert result.score >= 0.7
        assert result.level == ScoreLevel.HIGH

    def test_zero_overlap(self):
        req = make_request(question="apple orange banana", response="car truck bus")
        result = score_relevance(req)
        assert result.score == 0.0
        assert result.level == ScoreLevel.LOW

    def test_score_in_bounds(self):
        req = make_request()
        result = score_relevance(req)
        assert 0.0 <= result.score <= 1.0


# ---------------------------------------------------------------------------
# score_safety
# ---------------------------------------------------------------------------

class TestScoreSafety:
    def test_safe_response(self):
        req = make_request(response="The weather is nice today.")
        result = score_safety(req)
        assert result.score == 1.0
        assert result.level == ScoreLevel.HIGH

    def test_unsafe_keyword_reduces_score(self):
        req = make_request(response="This response contains the word harm.")
        result = score_safety(req)
        assert result.score < 1.0

    def test_multiple_unsafe_keywords(self):
        req = make_request(response="harm kill attack illegal weapon")
        safe_req = make_request(response="The weather is nice.")
        result_unsafe = score_safety(req)
        result_safe = score_safety(safe_req)
        assert result_unsafe.score < result_safe.score

    def test_score_never_below_zero(self):
        req = make_request(response=" ".join(["harm kill attack illegal dangerous weapon hate abuse"] * 10))
        result = score_safety(req)
        assert result.score >= 0.0


# ---------------------------------------------------------------------------
# score_completeness
# ---------------------------------------------------------------------------

class TestScoreCompleteness:
    def test_very_short_response(self):
        req = make_request(response="Yes.")
        result = score_completeness(req)
        assert result.score == 0.2
        assert result.level == ScoreLevel.LOW

    def test_medium_response(self):
        words = " ".join(["word"] * 25)
        req = make_request(response=words)
        result = score_completeness(req)
        assert result.score == 0.6

    def test_long_response(self):
        words = " ".join(["word"] * 110)
        req = make_request(response=words)
        result = score_completeness(req)
        assert result.score == 1.0
        assert result.level == ScoreLevel.HIGH


# ---------------------------------------------------------------------------
# compute_overall_score
# ---------------------------------------------------------------------------

class TestComputeOverallScore:
    def test_all_ones(self):
        g = GroundednessScore(score=1.0, level=ScoreLevel.HIGH)
        r = RelevanceScore(score=1.0, level=ScoreLevel.HIGH)
        s = SafetyScore(score=1.0, level=ScoreLevel.HIGH)
        c = CompletenessScore(score=1.0, level=ScoreLevel.HIGH)
        assert compute_overall_score(g, r, s, c) == 1.0

    def test_all_zeros(self):
        g = GroundednessScore(score=0.0, level=ScoreLevel.LOW)
        r = RelevanceScore(score=0.0, level=ScoreLevel.LOW)
        s = SafetyScore(score=0.0, level=ScoreLevel.LOW)
        c = CompletenessScore(score=0.0, level=ScoreLevel.LOW)
        assert compute_overall_score(g, r, s, c) == 0.0

    def test_weights_sum_to_one(self):
        assert abs(sum(METRIC_WEIGHTS.values()) - 1.0) < 1e-9

    def test_weighted_calculation(self):
        g = GroundednessScore(score=1.0, level=ScoreLevel.HIGH)
        r = RelevanceScore(score=0.0, level=ScoreLevel.LOW)
        s = SafetyScore(score=0.0, level=ScoreLevel.LOW)
        c = CompletenessScore(score=0.0, level=ScoreLevel.LOW)
        expected = round(METRIC_WEIGHTS["groundedness"], 4)
        assert compute_overall_score(g, r, s, c) == expected


# ---------------------------------------------------------------------------
# evaluate() integration
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_returns_evaluation_result(self):
        req = make_request()
        result = evaluate(req)
        assert isinstance(result, EvaluationResult)

    def test_result_has_all_metrics(self):
        req = make_request()
        result = evaluate(req)
        assert hasattr(result, "groundedness")
        assert hasattr(result, "relevance")
        assert hasattr(result, "safety")
        assert hasattr(result, "completeness")
        assert hasattr(result, "overall_score")

    def test_overall_score_in_bounds(self):
        req = make_request()
        result = evaluate(req)
        assert 0.0 <= result.overall_score <= 1.0

    def test_result_preserves_input(self):
        req = make_request(question="Test Q", response="Test R", context="Test C")
        result = evaluate(req)
        assert result.question == "Test Q"
        assert result.response == "Test R"
        assert result.context == "Test C"


# ---------------------------------------------------------------------------
# FastAPI endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    import os
    os.environ["DATABASE_PATH"] = "/tmp/test_evaluations.db"
    # Import after setting env var
    from api.dashboard_server import app
    with TestClient(app) as c:
        yield c


class TestEvaluateEndpoint:
    def test_post_evaluate_returns_201(self, client):
        payload = {
            "question": "What is Python?",
            "response": "Python is a high-level programming language.",
            "context": "Python is widely used for scripting and data science.",
        }
        res = client.post("/api/evaluate", json=payload)
        assert res.status_code == 201

    def test_post_evaluate_response_schema(self, client):
        payload = {
            "question": "What is AI?",
            "response": "AI stands for Artificial Intelligence.",
        }
        res = client.post("/api/evaluate", json=payload)
        data = res.json()
        for key in ("groundedness", "relevance", "safety", "completeness", "overall_score"):
            assert key in data

    def test_post_evaluate_missing_question_returns_422(self, client):
        res = client.post("/api/evaluate", json={"response": "some response"})
        assert res.status_code == 422

    def test_post_evaluate_missing_response_returns_422(self, client):
        res = client.post("/api/evaluate", json={"question": "some question"})
        assert res.status_code == 422


class TestHistoryEndpoint:
    def test_get_history_returns_list(self, client):
        res = client.get("/api/history")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_get_history_pagination(self, client):
        res = client.get("/api/history?limit=1&offset=0")
        assert res.status_code == 200
        assert len(res.json()) <= 1

    def test_get_history_item_not_found(self, client):
        res = client.get("/api/history/999999")
        assert res.status_code == 404


class TestMetricsEndpoint:
    def test_get_averages_returns_dict(self, client):
        res = client.get("/api/metrics/averages")
        assert res.status_code == 200
        data = res.json()
        for key in ("groundedness", "relevance", "safety", "completeness", "overall"):
            assert key in data

    def test_averages_values_in_range(self, client):
        res = client.get("/api/metrics/averages")
        data = res.json()
        for v in data.values():
            assert 0.0 <= v <= 1.0


class TestHealthEndpoint:
    def test_health_check(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
