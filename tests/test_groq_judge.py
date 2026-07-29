# test_groq_judge.py
# Covers the upgraded JSON-mode judge: response parsing (including malformed
# JSON), and that judge_all_metrics_async truly runs metrics concurrently via
# asyncio.gather. The Groq client is always mocked -- never a real API call.

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evaluation_pipeline.groq_judge import (
    judge_all_metrics_async,
    judge_metric_async,
    parse_json_judge_response,
)
from evaluation_pipeline.metric_definitions import EvaluationInput


def _mock_chat_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


def test_parse_json_judge_response_valid():
    score, reasoning = parse_json_judge_response('{"score": 0.85, "reasoning": "solid answer"}')
    assert score == 0.85
    assert reasoning == "solid answer"


def test_parse_json_judge_response_clamps_out_of_range_score():
    score, _ = parse_json_judge_response('{"score": 1.5, "reasoning": "x"}')
    assert score == 1.0


def test_parse_json_judge_response_malformed_json_falls_back():
    score, reasoning = parse_json_judge_response("not json at all")
    assert score == 0.5
    assert reasoning == "parse error"


def test_parse_json_judge_response_missing_score_key_falls_back():
    score, reasoning = parse_json_judge_response('{"reasoning": "no score field"}')
    assert score == 0.5
    assert reasoning == "parse error"


@pytest.mark.asyncio
async def test_judge_metric_async_uses_json_mode():
    mock_create = AsyncMock(return_value=_mock_chat_response('{"score": 0.9, "reasoning": "great"}'))

    with patch("evaluation_pipeline.groq_judge.async_client.chat.completions.create", mock_create):
        judge_input = EvaluationInput(question="q", context="c", ai_response="a")
        result = await judge_metric_async("groundedness", judge_input)

    assert result.score == 0.9
    assert result.reasoning == "great"
    assert result.metric_name == "groundedness"
    _, kwargs = mock_create.call_args
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_judge_metric_async_malformed_response_does_not_raise():
    mock_create = AsyncMock(return_value=_mock_chat_response("not valid json"))

    with patch("evaluation_pipeline.groq_judge.async_client.chat.completions.create", mock_create):
        judge_input = EvaluationInput(question="q", context="c", ai_response="a")
        result = await judge_metric_async("safety", judge_input)

    assert result.score == 0.5
    assert result.reasoning == "parse error"


@pytest.mark.asyncio
async def test_judge_all_metrics_async_runs_all_metrics_concurrently():
    call_count = 0

    async def fake_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _mock_chat_response('{"score": 0.7, "reasoning": "ok"}')

    with patch("evaluation_pipeline.groq_judge.async_client.chat.completions.create", new=fake_create):
        judge_input = EvaluationInput(question="q", context="c", ai_response="a", ground_truth="a")
        results = await judge_all_metrics_async(
            judge_input, ("groundedness", "correctness", "safety", "completeness")
        )

    assert call_count == 4
    assert set(results.keys()) == {"groundedness", "correctness", "safety", "completeness"}
    assert all(result.score == 0.7 for result in results.values())
