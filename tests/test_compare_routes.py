# test_compare_routes.py
# Exercises POST /compare, GET /runs, GET /runs/{id} with mocked adapters and
# a mocked judge — never touches a real provider or a real Groq call.


from typing import Any

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


VALID_PAYLOAD: dict[str, Any] = {
    "models": [
        {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
        {"provider": "openai", "model": "gpt-4o-mini"},
    ],
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
    assert len(data["results"]) == 2
    assert data["ranking"] == [m["model"] for m in VALID_PAYLOAD["models"]]
    assert data["results"][0]["rank"] == 1
    assert data["results"][0]["response_text"] == "fake response"
    assert data["results"][1]["response_text"] == "fake response"
    assert data["results"][0]["error"] is None
    assert set(data["results"][0]["judge_scores"].keys()) == {
        "groundedness",
        "correctness",
        "safety",
        "completeness",
    }
    assert data["results"][0]["tokens_per_sec"] is not None
    assert data["results"][0]["cost_per_task"] is not None


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
    errored = next(r for r in data["results"] if r["provider"] == "anthropic")
    working = next(r for r in data["results"] if r["provider"] == "openai")
    assert errored["error"] == "Anthropic API error"
    assert working["error"] is None
    assert working["rank"] == 1
    assert errored["rank"] == 2


def test_get_runs_returns_persisted_run(client):
    client.post("/compare", json=VALID_PAYLOAD, headers=VALID_HEADERS)

    resp = client.get("/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["runs"][0]["models"] == [m["model"] for m in VALID_PAYLOAD["models"]]


def test_get_single_run_returns_full_payload(client):
    create_resp = client.post("/compare", json=VALID_PAYLOAD, headers=VALID_HEADERS)
    run_id = create_resp.json()["run_id"]

    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["results"][0]["response_text"] == "fake response"


def test_get_run_not_found_returns_404(client):
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404


def test_list_suites_returns_metadata(client):
    resp = client.get("/suites")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_compare_reasoning_suite_aggregates_judge_scores(client):
    payload = {
        "models": [
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "openai", "model": "gpt-4o-mini"},
        ],
        "suite_id": "reasoning",
    }
    resp = client.post("/compare", json=payload, headers=VALID_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["results"][0]["judge_scores"]["correctness"]["score"] == 0.9
    assert data["results"][0]["code_pass_rate"] is None
    assert "[reasoning_001]" in data["results"][0]["response_text"]


def test_compare_coding_suite_uses_code_runner(client, monkeypatch):
    from metrics.code_runner import CodeRunResult

    def fake_run_code_test(code: str, unit_test: str, timeout_s: float = 5.0) -> CodeRunResult:
        return CodeRunResult(passed=True, error=None, timed_out=False)

    monkeypatch.setattr(compare_routes, "run_code_test", fake_run_code_test)

    payload = {
        "models": [
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "openai", "model": "gpt-4o-mini"},
        ],
        "suite_id": "coding",
    }
    resp = client.post("/compare", json=payload, headers=VALID_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["results"][0]["code_pass_rate"] == 1.0
    assert data["results"][0]["judge_scores"] == {}


def test_compare_suite_not_found_returns_404(client):
    payload = {
        "models": [
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "openai", "model": "gpt-4o-mini"},
        ],
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
    assert data["results"][0]["consistency"] == 1.0


def test_provider_auth_error_never_leaks_key_over_http(client, monkeypatch):
    """End-to-end guard on the whole exposure chain.

    A provider auth failure echoes the submitted key back in its exception
    message. That message becomes ModelResult.error, is persisted, and is then
    served from GET /runs/{run_id} — which requires no authentication. The key
    must survive none of those hops.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from providers.openai_adapter import OpenAIAdapter

    byok_key = "sk-proj-" + "aB3" * 20 + "_xY-9"

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError(f"Incorrect API key provided: {byok_key}")
    )

    monkeypatch.setitem(compare_routes._ADAPTERS, "openai", OpenAIAdapter())

    with patch("providers.openai_adapter.AsyncOpenAI", return_value=mock_client):
        resp = client.post(
            "/compare",
            json=VALID_PAYLOAD,
            headers={**VALID_HEADERS, "X-OpenAI-Key": byok_key},
        )

    assert resp.status_code == 200
    assert byok_key not in resp.text

    run_id = resp.json()["run_id"]
    history = client.get(f"/runs/{run_id}")
    assert history.status_code == 200
    assert byok_key not in history.text
    assert "[REDACTED]" in next(r["error"] for r in history.json()["results"] if r["error"])


def test_compare_three_models_ranks_all(client, monkeypatch):
    monkeypatch.setitem(compare_routes._ADAPTERS, "gemini", FakeAdapter(text="third response"))
    payload = {
        "models": [
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-1.5-flash"},
        ],
        "prompt": "hello",
    }
    headers = {**VALID_HEADERS, "X-Gemini-Key": "AIza" + "S" * 35}
    resp = client.post("/compare", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 3
    assert len(data["ranking"]) == 3
    assert sorted(r["rank"] for r in data["results"]) == [1, 1, 1]  # identical fake scores tie


def test_compare_publishes_sse_event_sequence_for_three_models(client, monkeypatch):
    """Locks in the SSE wire contract: started -> model_done (once per model,
    each carrying its submission slot) -> judge_done -> complete, in that
    order, published via compare_routes._publish. This is the only test tying
    the backend event-publishing side to the documented event contract that
    the frontend's useEventSource.ts also relies on."""
    monkeypatch.setitem(compare_routes._ADAPTERS, "gemini", FakeAdapter(text="third response"))

    recorded_events: list[dict] = []

    async def fake_publish(run_id: str, event: dict) -> None:
        recorded_events.append(event)

    monkeypatch.setattr(compare_routes, "_publish", fake_publish)

    payload = {
        "models": [
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-1.5-flash"},
        ],
        "prompt": "hello",
    }
    headers = {**VALID_HEADERS, "X-Gemini-Key": "AIza" + "S" * 35}
    resp = client.post("/compare", json=payload, headers=headers)
    assert resp.status_code == 200

    event_names = [event["event"] for event in recorded_events]
    assert event_names == ["started", "model_done", "model_done", "model_done", "judge_done", "complete"]

    model_done_events = [event for event in recorded_events if event["event"] == "model_done"]
    assert {event["slot"] for event in model_done_events} == {"1", "2", "3"}
    assert all("latency_ms" in event for event in model_done_events)
    assert all(event["run_id"] == resp.json()["run_id"] for event in recorded_events)


def test_compare_missing_key_for_any_provider_400s_before_calls(client):
    payload = {
        "models": [
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "gemini", "model": "gemini-1.5-flash"},
        ],
        "prompt": "hello",
    }
    resp = client.post("/compare", json=payload, headers={"X-Anthropic-Key": "sk-ant-test"})
    assert resp.status_code == 400
    assert "gemini" in resp.json()["detail"]


async def _seed_legacy_run() -> None:
    """Insert a pre-migration-shaped run: legacy runs columns filled,
    ranking NULL, slots 'model_a'/'model_b'."""
    await arena_store.save_model_result({
        "id": "legacy-mr-a", "run_id": "legacy-run", "slot": "model_a",
        "model_name": "claude-3-5-haiku-20241022", "provider": "anthropic",
        "response_text": "old answer A", "input_tokens": 10, "output_tokens": 20,
        "latency_ms": 900.0, "cost_usd": 0.001, "code_pass_rate": None,
        "consistency": None, "error": None,
    })
    await arena_store.save_model_result({
        "id": "legacy-mr-b", "run_id": "legacy-run", "slot": "model_b",
        "model_name": "gpt-4o-mini", "provider": "openai",
        "response_text": "old answer B", "input_tokens": 10, "output_tokens": 20,
        "latency_ms": 800.0, "cost_usd": 0.002, "code_pass_rate": None,
        "consistency": None, "error": None,
    })
    await arena_store.save_metric_score({
        "id": "legacy-ms-1", "model_result_id": "legacy-mr-a",
        "metric_name": "correctness", "score": 0.9, "reasoning": "good",
    })
    await arena_store.save_metric_score({
        "id": "legacy-ms-2", "model_result_id": "legacy-mr-b",
        "metric_name": "correctness", "score": 0.5, "reasoning": "meh",
    })
    # Raw insert mimicking a migrated v1 row: legacy cols set, ranking NULL.
    import aiosqlite
    async with aiosqlite.connect(arena_store.DB_PATH) as db:
        await db.execute(
            "INSERT INTO runs (id, suite_id, prompt, model_a, model_b, provider_a, provider_b, winner) "
            "VALUES ('legacy-run', NULL, 'old prompt', 'claude-3-5-haiku-20241022', 'gpt-4o-mini', "
            "'anthropic', 'openai', 'model_a')"
        )
        await db.commit()


def test_legacy_two_model_run_still_readable(client):
    """A pre-migration run (legacy columns + model_a/model_b slots, no ranking)
    must render through the new list-shaped API. The client fixture has already
    initialized/migrated the tmp DB by the time the test body runs, so seeding
    with asyncio.run() here is safe."""
    import asyncio
    asyncio.run(_seed_legacy_run())

    detail = client.get("/runs/legacy-run")
    assert detail.status_code == 200
    data = detail.json()
    assert len(data["results"]) == 2
    assert data["ranking"][0] == "claude-3-5-haiku-20241022"  # 0.9 beats 0.5
    assert data["results"][0]["rank"] == 1
    assert data["results"][0]["cost_per_task"] is not None    # derived retroactively

    listing = client.get("/runs")
    assert listing.status_code == 200
    row = next(r for r in listing.json()["runs"] if r["run_id"] == "legacy-run")
    assert row["models"] == ["claude-3-5-haiku-20241022", "gpt-4o-mini"]
    assert row["winner"] == "claude-3-5-haiku-20241022"

