# compare_routes.py
# The arena's core endpoint: fan a single prompt out to two providers
# concurrently, judge both responses, compute cost/latency, persist, respond.

import asyncio
import json
import statistics
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from api.models import (
    CompareRequest,
    CompareResponse,
    JudgeScore,
    ModelResult,
    RunsListResponse,
    RunSummary,
    SuiteMetadata,
)
from database import arena_store
from evaluation_pipeline.groq_judge import judge_metric
from evaluation_pipeline.metric_definitions import EvaluationInput
from providers.anthropic_adapter import AnthropicAdapter
from providers.base import ModelProvider, ModelResponse
from providers.gemini_adapter import GeminiAdapter
from providers.openai_adapter import OpenAIAdapter

router = APIRouter()

_ADAPTERS: dict[str, ModelProvider] = {
    "anthropic": AnthropicAdapter(),
    "openai": OpenAIAdapter(),
    "gemini": GeminiAdapter(),
}

_KEY_HEADERS = {
    "anthropic": "x-anthropic-key",
    "openai": "x-openai-key",
    "gemini": "x-gemini-key",
}

_JUDGE_METRICS = ("groundedness", "relevance", "safety", "completeness")

# In-memory pub/sub for live SSE progress. Keyed by run_id. Not persisted —
# purely a UI convenience; the durable record lives in arena_store.
_event_queues: dict[str, asyncio.Queue] = {}

SUITES_DIR = Path(__file__).resolve().parent.parent / "suites"


async def _publish(run_id: str, event: dict) -> None:
    queue = _event_queues.setdefault(run_id, asyncio.Queue())
    await queue.put(event)


def _extract_api_key(request: Request, provider: str) -> str:
    header_name = _KEY_HEADERS[provider]
    api_key = request.headers.get(header_name)
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required header '{header_name}' for provider '{provider}'.",
        )
    return api_key


async def _judge_response(prompt: str, response_text: str) -> dict[str, JudgeScore]:
    """Score one model's response against all legacy metrics.

    Runs the (currently synchronous) Groq judge calls off the event loop via
    asyncio.to_thread so the API never blocks. TODO(Phase 2): replace with a
    true async, JSON-mode judge using asyncio.gather.
    """
    judge_input = EvaluationInput(question=prompt, context="", ai_response=response_text)

    results = await asyncio.gather(
        *(asyncio.to_thread(judge_metric, metric, judge_input) for metric in _JUDGE_METRICS)
    )

    return {
        result.metric_name: JudgeScore(score=result.score, reasoning=result.reasoning)
        for result in results
    }


async def _run_one_model(
    slot: str,
    provider: str,
    model: str,
    prompt: str,
    api_key: str,
    run_id: str,
) -> ModelResult:
    from metrics.cost import calculate_cost

    adapter = _ADAPTERS[provider]
    response: ModelResponse = await adapter.complete(prompt=prompt, api_key=api_key, model=model)

    await _publish(run_id, {"event": f"{slot}_done", "run_id": run_id, "latency_ms": response.latency_ms})

    judge_scores: dict[str, JudgeScore] = {}
    if response.error is None:
        judge_scores = await _judge_response(prompt, response.text)

    cost_usd = calculate_cost(model, response.input_tokens, response.output_tokens)

    return ModelResult(
        provider=provider,
        model=model,
        response_text=response.text,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        latency_ms=response.latency_ms,
        cost_usd=cost_usd,
        judge_scores=judge_scores,
        code_pass_rate=None,
        consistency=None,
        error=response.error,
    )


def _average_judge_score(result: ModelResult) -> float | None:
    if not result.judge_scores:
        return None
    return statistics.mean(score.score for score in result.judge_scores.values())


def _determine_winner(result_a: ModelResult, result_b: ModelResult) -> str:
    if result_a.error and result_b.error:
        return "tie"
    if result_a.error:
        return "model_b"
    if result_b.error:
        return "model_a"

    avg_a = _average_judge_score(result_a)
    avg_b = _average_judge_score(result_b)
    if avg_a is None or avg_b is None or avg_a == avg_b:
        return "tie"
    return "model_a" if avg_a > avg_b else "model_b"


@router.post("/compare", response_model=CompareResponse)
async def compare(request: Request, body: CompareRequest) -> CompareResponse:
    if body.suite_id is not None:
        raise HTTPException(
            status_code=501,
            detail="Suite-based comparisons are not yet implemented (Phase 2).",
        )

    api_key_a = _extract_api_key(request, body.provider_a)
    api_key_b = _extract_api_key(request, body.provider_b)

    run_id = body.run_id or str(uuid.uuid4())
    prompt = body.prompt or ""

    await _publish(run_id, {"event": "started", "run_id": run_id})

    result_a, result_b = await asyncio.gather(
        _run_one_model("model_a", body.provider_a, body.model_a, prompt, api_key_a, run_id),
        _run_one_model("model_b", body.provider_b, body.model_b, prompt, api_key_b, run_id),
    )

    await _publish(run_id, {"event": "judge_done", "run_id": run_id})

    winner = _determine_winner(result_a, result_b)
    created_at = datetime.now(UTC).isoformat()

    await arena_store.save_run(
        {
            "id": run_id,
            "suite_id": None,
            "prompt": prompt,
            "model_a": body.model_a,
            "model_b": body.model_b,
            "provider_a": body.provider_a,
            "provider_b": body.provider_b,
            "winner": winner,
        }
    )

    for slot, result in (("model_a", result_a), ("model_b", result_b)):
        model_result_id = str(uuid.uuid4())
        await arena_store.save_model_result(
            {
                "id": model_result_id,
                "run_id": run_id,
                "slot": slot,
                "model_name": result.model,
                "provider": result.provider,
                "response_text": result.response_text,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "latency_ms": result.latency_ms,
                "cost_usd": result.cost_usd,
                "code_pass_rate": result.code_pass_rate,
                "consistency": result.consistency,
                "error": result.error,
            }
        )
        for metric_name, judge_score in result.judge_scores.items():
            await arena_store.save_metric_score(
                {
                    "id": str(uuid.uuid4()),
                    "model_result_id": model_result_id,
                    "metric_name": metric_name,
                    "score": judge_score.score,
                    "reasoning": judge_score.reasoning,
                }
            )

    await _publish(run_id, {"event": "complete", "run_id": run_id})
    _event_queues.pop(run_id, None)

    return CompareResponse(
        run_id=run_id,
        model_a=result_a,
        model_b=result_b,
        winner=winner,
        created_at=created_at,
    )


@router.get("/suites", response_model=list[SuiteMetadata])
def list_suites() -> list[SuiteMetadata]:
    suites: list[SuiteMetadata] = []
    if not SUITES_DIR.exists():
        return suites

    display_names = {
        "coding": "Coding Ability",
        "reasoning": "Reasoning",
        "rag_faithfulness": "RAG Faithfulness",
        "safety": "Safety",
    }

    for suite_file in sorted(SUITES_DIR.glob("*.json")):
        suite_id = suite_file.stem
        try:
            items = json.loads(suite_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        suites.append(
            SuiteMetadata(
                id=suite_id,
                name=display_names.get(suite_id, suite_id.replace("_", " ").title()),
                item_count=len(items) if isinstance(items, list) else 0,
            )
        )
    return suites


@router.get("/runs", response_model=RunsListResponse)
async def list_runs(limit: int = 50, offset: int = 0) -> RunsListResponse:
    rows = await arena_store.get_all_runs(limit=limit, offset=offset)
    return RunsListResponse(
        total=len(rows),
        runs=[
            RunSummary(
                run_id=row["id"],
                model_a=row["model_a"],
                model_b=row["model_b"],
                winner=row["winner"],
                created_at=row["created_at"],
            )
            for row in rows
        ],
    )


@router.get("/runs/{run_id}", response_model=CompareResponse)
async def get_run(run_id: str) -> CompareResponse:
    run = await arena_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    model_results = await arena_store.get_model_results_for_run(run_id)
    if len(model_results) != 2:
        raise HTTPException(status_code=500, detail="Run has incomplete data.")

    results_by_slot: dict[str, ModelResult] = {}
    for row in model_results:
        scores = await arena_store.get_metric_scores_for_result(row["id"])
        judge_scores = {
            score["metric_name"]: JudgeScore(score=score["score"], reasoning=score["reasoning"] or "")
            for score in scores
        }
        results_by_slot[row["slot"]] = ModelResult(
            provider=row["provider"],
            model=row["model_name"],
            response_text=row["response_text"] or "",
            input_tokens=row["input_tokens"] or 0,
            output_tokens=row["output_tokens"] or 0,
            latency_ms=row["latency_ms"] or 0.0,
            cost_usd=row["cost_usd"] or 0.0,
            judge_scores=judge_scores,
            code_pass_rate=row["code_pass_rate"],
            consistency=row["consistency"],
            error=row["error"],
        )

    return CompareResponse(
        run_id=run["id"],
        model_a=results_by_slot["model_a"],
        model_b=results_by_slot["model_b"],
        winner=run["winner"] or "tie",
        created_at=str(run["created_at"]),
    )


@router.get("/stream/{run_id}")
async def stream_run(run_id: str) -> EventSourceResponse:
    async def event_generator():
        queue = _event_queues.setdefault(run_id, asyncio.Queue())
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
                yield {"event": event.get("event", "message"), "data": json.dumps(event)}
                if event.get("event") in ("complete", "error"):
                    break
        except TimeoutError:
            yield {"event": "timeout", "data": json.dumps({"run_id": run_id})}

    return EventSourceResponse(event_generator())
