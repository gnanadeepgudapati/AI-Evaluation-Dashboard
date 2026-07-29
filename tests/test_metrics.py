# test_metrics.py
# Deterministic metric math — cost and latency aggregation.

from metrics.cost import calculate_cost
from metrics.latency import p50


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
