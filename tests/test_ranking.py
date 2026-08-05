import pytest

from api.compare_routes import _enrich_results, _rank_results, _task_count
from api.models import JudgeScore, ModelResult


def _result(model: str, score: float | None, error: str | None = None, **kw) -> ModelResult:
    scores = {} if score is None else {"correctness": JudgeScore(score=score, reasoning="")}
    return ModelResult(
        provider="openai", model=model, response_text="x",
        input_tokens=10, output_tokens=100, latency_ms=1000.0, cost_usd=0.01,
        judge_scores=scores, error=error, **kw,
    )


def test_rank_orders_by_aggregate_desc():
    ordered, ranking = _rank_results([_result("low", 0.5), _result("high", 0.9), _result("mid", 0.7)])
    assert ranking == ["high", "mid", "low"]
    assert [r.rank for r in ordered] == [1, 2, 3]
    assert ordered[0].aggregate_score == pytest.approx(0.9)


def test_equal_scores_share_rank_competition_style():
    ordered, _ = _rank_results([_result("a", 0.9), _result("b", 0.9), _result("c", 0.5)])
    assert [r.rank for r in ordered] == [1, 1, 3]


def test_errored_models_rank_last():
    ordered, ranking = _rank_results([_result("dead", None, error="boom"), _result("ok", 0.4)])
    assert ranking == ["ok", "dead"]
    assert ordered[-1].error == "boom"
    assert ordered[-1].aggregate_score is None


def test_code_pass_rate_counts_as_aggregate_when_no_judge_scores():
    coding = _result("coder", None, code_pass_rate=0.8)
    ordered, ranking = _rank_results([coding, _result("talker", 0.6)])
    assert ranking == ["coder", "talker"]  # 0.8 pass-rate beats 0.6 judge avg


def test_task_count_prompt_mode():
    assert _task_count(None, 1) == 1
    assert _task_count(None, 3) == 3


def test_task_count_missing_suite_falls_back():
    assert _task_count("no_such_suite", 2) == 2


def test_enrich_fills_derived_fields():
    r = _result("m", 0.9)
    _enrich_results([r], suite_id=None, consistency_runs=1)
    assert r.tokens_per_sec == pytest.approx(100.0)  # 100 tok / 1s
    assert r.cost_per_task == pytest.approx(0.01)
    assert r.cost_per_1k_tasks == pytest.approx(10.0)


def test_enrich_skips_errored():
    r = _result("dead", None, error="boom")
    _enrich_results([r], suite_id=None, consistency_runs=1)
    assert r.tokens_per_sec is None and r.cost_per_task is None
