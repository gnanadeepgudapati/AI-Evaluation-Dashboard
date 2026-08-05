# models.py
# Pydantic v2 request/response contracts for the comparison arena API.

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Provider = Literal["anthropic", "openai", "gemini"]


class JudgeScore(BaseModel):
    score: float
    reasoning: str


class ModelSpec(BaseModel):
    provider: Provider
    model: str


class ModelResult(BaseModel):
    provider: str
    model: str
    response_text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    judge_scores: dict[str, JudgeScore] = Field(default_factory=dict)
    code_pass_rate: float | None = None
    consistency: float | None = None
    error: str | None = None
    # Derived at read/response time — never stored (see design spec §2):
    aggregate_score: float | None = None
    rank: int | None = None
    cost_per_task: float | None = None
    cost_per_1k_tasks: float | None = None
    tokens_per_sec: float | None = None


class CompareRequest(BaseModel):
    models: list[ModelSpec] = Field(min_length=2, max_length=4)
    prompt: str | None = None
    suite_id: str | None = None
    consistency_runs: int = 1
    run_id: str | None = None

    @model_validator(mode="after")
    def _validate_prompt_xor_suite(self) -> "CompareRequest":
        if bool(self.prompt) == bool(self.suite_id):
            raise ValueError("Exactly one of `prompt` or `suite_id` must be provided.")
        if self.consistency_runs not in (1, 2, 3):
            raise ValueError("consistency_runs must be 1, 2, or 3.")
        return self


class CompareResponse(BaseModel):
    run_id: str
    results: list[ModelResult]   # ordered best -> worst (rank 1 first)
    ranking: list[str]           # model names, best -> worst
    created_at: str


class SuiteMetadata(BaseModel):
    id: str
    name: str
    item_count: int


class RunSummary(BaseModel):
    run_id: str
    models: list[str]
    winner: str | None           # model NAME (ranking[0]), or "tie" on legacy ties
    created_at: str


class RunsListResponse(BaseModel):
    total: int
    runs: list[RunSummary]
