# test_compare_routes.py
# Exercises POST /compare, GET /runs, GET /runs/{id} with mocked adapters and
# a mocked judge — never touches a real provider or a real Groq call.


import pytest
from fastapi.testclient import TestClient

import api.compare_routes as compare_routes
import database.arena_store as arena_store
from evaluation_pipeline.metric_definitions import MetricResult
from providers.base import ModelResponse


class FakeAdapter:
    """Stand-in for a real provider adapter — never calls a network API."""

    def __init__(self, text: str = "fake response", error: str | None = None):
        self.text = text
        self.error = error

    async def complete(self, prompt: str, api_key: str, model: str, timeout_s: float = 30.0) -> ModelResponse:
        return ModelResponse(
            text=self.text,
            input_tokens=10,
            output_tokens=20,
            latency_ms=5.0,
            error=self.error,
        )


async def fake_judge_all_metrics_async(
    judge_input, metrics: tuple[str, ...] = ("groundedness", "correctness", "safety", "completeness")
) -> dict[str, MetricResult]:
    return {
        metric: MetricResult(metric_name=metric, score=0.9, reasoning="looks good", passed=True)
        for metric in metrics
    }


VALID_PAYLOAD = {
    "model_a": "claude-3-5-haiku-20241022",
    "model_b": "gpt-4o-mini",
    "provider_a": "anthropic",
    "provider_b": "openai",
    "prompt": "Explain recursion with a Python example",
}

VALID_HEADERS = {
    "X-Anthropic-Key": "sk-ant-test-key",
    "X-OpenAI-Key": "sk-test-key-1234567890123456",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(arena_store, "DB_PATH", str(tmp_path / "arena_test.db"))
    monkeypatch.setitem(compare_routes._ADAPTERS, "anthropic", FakeAdapter())
    monkeypatch.setitem(compare_routes._ADAPTERS, "openai", FakeAdapter())
    monkeypatch.setattr(compare_routes, "judge_all_metrics_async", fake_judge_all_metrics_async)

    from api.dashboard_server import app

    with TestClient(app) as test_client:
        yield test_client


def test_compare_success_returns_full_response(client):
    resp = client.post("/compare", json=VALID_PAYLOAD, headers=VALID_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["winner"] in ("model_a", "model_b", "tie")
    assert data["model_a"]["response_text"] == "fake response"
    assert data["model_b"]["response_text"] == "fake response"
    assert data["model_a"]["error"] is None
    assert set(data["model_a"]["judge_scores"].keys()) == {
        "groundedness",
        "correctness",
        "safety",
        "completeness",
    }


def test_compare_missing_api_key_header_returns_400(client):
    resp = client.post("/compare", json=VALID_PAYLOAD, headers={"X-Anthropic-Key": "sk-ant-test"})
    assert resp.status_code == 400


def test_compare_requires_prompt_xor_suite(client):
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "prompt"}
    resp = client.post("/compare", json=payload, headers=VALID_HEADERS)
    assert resp.status_code == 422


def test_compare_both_prompt_and_suite_rejected(client):
    payload = {**VALID_PAYLOAD, "suite_id": "reasoning"}
    resp = client.post("/compare", json=payload, headers=VALID_HEADERS)
    assert resp.status_code == 422


def test_compare_provider_failure_does_not_crash_run(client, monkeypatch):
    monkeypatch.setitem(compare_routes._ADAPTERS, "anthropic", FakeAdapter(text="", error="Anthropic API error"))

    resp = client.post("/compare", json=VALID_PAYLOAD, headers=VALID_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["model_a"]["error"] == "Anthropic API error"
    assert data["winner"] == "model_b"


def test_get_runs_returns_persisted_run(client):
    client.post("/compare", json=VALID_PAYLOAD, headers=VALID_HEADERS)

    resp = client.get("/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["runs"][0]["model_a"] == "claude-3-5-haiku-20241022"


def test_get_single_run_returns_full_payload(client):
    create_resp = client.post("/compare", json=VALID_PAYLOAD, headers=VALID_HEADERS)
    run_id = create_resp.json()["run_id"]

    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["model_a"]["response_text"] == "fake response"


def test_get_run_not_found_returns_404(client):
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404


def test_list_suites_returns_metadata(client):
    resp = client.get("/suites")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_compare_reasoning_suite_aggregates_judge_scores(client):
    payload = {
        "model_a": "claude-3-5-haiku-20241022",
        "model_b": "gpt-4o-mini",
        "provider_a": "anthropic",
        "provider_b": "openai",
        "suite_id": "reasoning",
    }
    resp = client.post("/compare", json=payload, headers=VALID_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["model_a"]["judge_scores"]["correctness"]["score"] == 0.9
    assert data["model_a"]["code_pass_rate"] is None
    assert "[reasoning_001]" in data["model_a"]["response_text"]


def test_compare_coding_suite_uses_code_runner(client, monkeypatch):
    from metrics.code_runner import CodeRunResult

    def fake_run_code_test(code: str, unit_test: str, timeout_s: float = 5.0) -> CodeRunResult:
        return CodeRunResult(passed=True, error=None, timed_out=False)

    monkeypatch.setattr(compare_routes, "run_code_test", fake_run_code_test)

    payload = {
        "model_a": "claude-3-5-haiku-20241022",
        "model_b": "gpt-4o-mini",
        "provider_a": "anthropic",
        "provider_b": "openai",
        "suite_id": "coding",
    }
    resp = client.post("/compare", json=payload, headers=VALID_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["model_a"]["code_pass_rate"] == 1.0
    assert data["model_a"]["judge_scores"] == {}


def test_compare_suite_not_found_returns_404(client):
    payload = {
        "model_a": "claude-3-5-haiku-20241022",
        "model_b": "gpt-4o-mini",
        "provider_a": "anthropic",
        "provider_b": "openai",
        "suite_id": "does_not_exist",
    }
    resp = client.post("/compare", json=payload, headers=VALID_HEADERS)
    assert resp.status_code == 404


def test_compare_consistency_runs_computes_consistency_score(client):
    payload = {**VALID_PAYLOAD, "consistency_runs": 2}
    resp = client.post("/compare", json=payload, headers=VALID_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    # Fake judge always returns 0.9 -> zero variance -> consistency == 1.0
    assert data["model_a"]["consistency"] == 1.0

