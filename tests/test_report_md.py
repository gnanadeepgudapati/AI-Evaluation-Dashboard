from api.models import CompareResponse, JudgeScore, ModelResult
from api.report_md import render_markdown_report
from tests.test_compare_routes import client  # noqa: F401, F811


def _response() -> CompareResponse:
    winner = ModelResult(
        provider="openai", model="gpt-4o-mini", response_text="hi", input_tokens=10,
        output_tokens=100, latency_ms=1000.0, cost_usd=0.01,
        judge_scores={"correctness": JudgeScore(score=0.9, reasoning="right")},
        aggregate_score=0.9, rank=1, cost_per_task=0.01, cost_per_1k_tasks=10.0,
        tokens_per_sec=100.0,
    )
    loser = ModelResult(
        provider="anthropic", model="claude-3-5-haiku-20241022", response_text="hello",
        input_tokens=10, output_tokens=80, latency_ms=1500.0, cost_usd=0.02,
        judge_scores={"correctness": JudgeScore(score=0.5, reasoning="partial")},
        aggregate_score=0.5, rank=2, cost_per_task=0.02, cost_per_1k_tasks=20.0,
        tokens_per_sec=53.3,
    )
    return CompareResponse(
        run_id="abc12345-0000", results=[winner, loser],
        ranking=["gpt-4o-mini", "claude-3-5-haiku-20241022"],
        created_at="2026-08-05T12:00:00+00:00",
    )


def test_report_contains_verdict_leaderboard_and_responses():
    md = render_markdown_report(_response(), suite_id=None, prompt="say hi", consistency_runs=1)
    assert "# LLM Comparison Report" in md
    assert "**Winner:** gpt-4o-mini" in md
    assert "| Rank |" in md                      # leaderboard table header
    assert "| 1 | gpt-4o-mini |" in md
    assert "$10.0000" in md                      # cost per 1k tasks
    assert "say hi" in md                        # prompt echoed
    assert "### 1. gpt-4o-mini (openai)" in md   # response section


def test_report_notes_errored_model():
    resp = _response()
    resp.results[1].error = "AuthenticationError: [REDACTED]"
    md = render_markdown_report(resp, suite_id=None, prompt="say hi", consistency_runs=1)
    assert "AuthenticationError" in md
    assert "failed" in md.lower()


def test_report_md_endpoint(client):  # noqa: F811
    """Endpoint variant — reuses the client fixture from test_compare_routes."""
    from tests.test_compare_routes import VALID_HEADERS, VALID_PAYLOAD

    run = client.post("/compare", json=VALID_PAYLOAD, headers=VALID_HEADERS).json()
    resp = client.get(f"/runs/{run['run_id']}/report.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "attachment" in resp.headers["content-disposition"]
    assert "# LLM Comparison Report" in resp.text
