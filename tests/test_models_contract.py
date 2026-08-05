import pytest
from pydantic import ValidationError

from api.models import CompareRequest, ModelSpec

TWO = [
    ModelSpec(provider="anthropic", model="claude-3-5-haiku-20241022"),
    ModelSpec(provider="openai", model="gpt-4o-mini"),
]


def test_two_models_with_prompt_is_valid():
    req = CompareRequest(models=TWO, prompt="hi")
    assert len(req.models) == 2


def test_four_models_is_valid():
    req = CompareRequest(models=TWO * 2, prompt="hi")  # duplicates are legal
    assert len(req.models) == 4


def test_one_model_rejected():
    with pytest.raises(ValidationError):
        CompareRequest(models=TWO[:1], prompt="hi")


def test_five_models_rejected():
    with pytest.raises(ValidationError):
        CompareRequest(models=TWO * 2 + TWO[:1], prompt="hi")


def test_prompt_xor_suite_still_enforced():
    with pytest.raises(ValidationError):
        CompareRequest(models=TWO, prompt="hi", suite_id="reasoning")
    with pytest.raises(ValidationError):
        CompareRequest(models=TWO)


def test_consistency_runs_bounds():
    with pytest.raises(ValidationError):
        CompareRequest(models=TWO, prompt="hi", consistency_runs=4)
