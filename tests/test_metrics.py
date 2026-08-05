# test_metrics.py
# Deterministic metric math — cost and latency aggregation.

import pytest

from metrics.cost import calculate_cost, cost_per_1k_tasks, cost_per_task
from metrics.latency import p50, tokens_per_sec


def test_calculate_cost_known_value_gpt_4o_mini():
    # 1000 input tokens @ $0.15/1M + 500 output tokens @ $0.60/1M
    expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
    assert calculate_cost("gpt-4o-mini", 1000, 500) == expected


def test_calculate_cost_known_value_claude_haiku():
    expected = (2000 * 0.80 + 1000 * 4.00) / 1_000_000
    assert calculate_cost("claude-3-5-haiku-20241022", 2000, 1000) == expected


def test_calculate_cost_known_value_gemini_flash():
    expected = (500 * 0.075 + 200 * 0.30) / 1_000_000
    assert calculate_cost("gemini-1.5-flash", 500, 200) == expected


def test_calculate_cost_unknown_model_returns_zero():
    assert calculate_cost("some-brand-new-model-nobody-has-priced", 1000, 1000) == 0.0


def test_calculate_cost_zero_tokens():
    assert calculate_cost("gpt-4o-mini", 0, 0) == 0.0


def test_p50_odd_count():
    assert p50([100.0, 200.0, 300.0]) == 200.0


def test_p50_even_count():
    assert p50([100.0, 200.0, 300.0, 400.0]) == 250.0


def test_p50_single_value():
    assert p50([42.0]) == 42.0


def test_p50_empty_list():
    assert p50([]) == 0.0


def test_cost_per_task_divides_by_task_count():
    assert cost_per_task(0.05, 5) == pytest.approx(0.01)


def test_cost_per_task_zero_count_returns_none():
    assert cost_per_task(0.05, 0) is None


def test_cost_per_1k_tasks_projects():
    assert cost_per_1k_tasks(0.05, 5) == pytest.approx(10.0)


def test_tokens_per_sec_basic():
    # 200 output tokens over one 2000ms call -> 100 tok/s
    assert tokens_per_sec(200, 2000.0) == pytest.approx(100.0)


def test_tokens_per_sec_averages_over_calls():
    # 600 total tokens over 3 calls at p50 2000ms -> 200/call -> 100 tok/s
    assert tokens_per_sec(600, 2000.0, call_count=3) == pytest.approx(100.0)


def test_tokens_per_sec_zero_latency_returns_none():
    assert tokens_per_sec(200, 0.0) is None
