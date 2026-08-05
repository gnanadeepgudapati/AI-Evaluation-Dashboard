# compare_routes.py
# The arena's core endpoint: fan a single prompt out to two providers
# concurrently, judge both responses, compute cost/latency, persist, respond.

import asyncio
import json
import re
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
from evaluation_pipeline.groq_judge import judge_all_metrics_async
from evaluation_pipeline.metric_definitions import EvaluationInput
from metrics.code_runner import run_code_test
from metrics.cost import calculate_cost, cost_per_1k_tasks, cost_per_task
from metrics.latency import p50, tokens_per_sec
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

_JUDGE_METRICS = ("groundedness", "correctness", "safety", "completeness")

# Which judge metrics apply to each built-in suite. The coding suite uses no
# judge metrics at all -- it is scored purely by code_runner's pass rate.
SUITE_JUDGE_METRICS: dict[str, tuple[str, ...]] = {
    "reasoning": ("correctness", "completeness"),
    "rag_faithfulness": ("groundedness", "correctness", "completeness"),
    "safety": ("safety",),
    "coding": (),
}

_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)

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


async def _judge_response(
    prompt: str, response_text: str, metrics: tuple[str, ...] = _JUDGE_METRICS
) -> dict[str, JudgeScore]:
    """Score one model's response with the async, JSON-mode judge (asyncio.gather)."""
    judge_input = EvaluationInput(question=prompt, context="", ai_response=response_text)
    results = await judge_all_metrics_async(judge_input, metrics)
    return {name: JudgeScore(score=result.score, reasoning=result.reasoning) for name, result in results.items()}


async def _run_one_model(
    slot: str,
    provider: str,
    model: str,
    prompt: str,
    api_key: str,
    run_id: str,
    consistency_runs: int = 1,
) -> ModelResult:
    adapter = _ADAPTERS[provider]

    responses: list[ModelResponse] = []
    for _ in range(consistency_runs):
        responses.append(await adapter.complete(prompt=prompt, api_key=api_key, model=model))

    primary = responses[0]
    await _publish(run_id, {"event": "model_done", "run_id": run_id, "slot": slot, "latency_ms": primary.latency_ms})

    judge_scores: dict[str, JudgeScore] = {}
    consistency: float | None = None
    if primary.error is None:
        judge_scores = await _judge_response(prompt, primary.text)
        run_avg_scores = [statistics.mean(score.score for score in judge_scores.values())]

        for extra_response in responses[1:]:
            if extra_response.error is not None:
                continue
            extra_scores = await _judge_response(prompt, extra_response.text)
            if extra_scores:
                run_avg_scores.append(statistics.mean(score.score for score in extra_scores.values()))

        if len(run_avg_scores) > 1:
            consistency = max(0.0, 1 - statistics.pstdev(run_avg_scores))

    total_input_tokens = sum(r.input_tokens for r in responses)
    total_output_tokens = sum(r.output_tokens for r in responses)
    cost_usd = calculate_cost(model, total_input_tokens, total_output_tokens)

    return ModelResult(
        provider=provider,
        model=model,
        response_text=primary.text,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        latency_ms=p50([r.latency_ms for r in responses]),
        cost_usd=cost_usd,
        judge_scores=judge_scores,
        code_pass_rate=None,
        consistency=consistency,
        error=primary.error,
    )


def _load_suite_items(suite_id: str) -> list[dict]:
    path = SUITES_DIR / f"{suite_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Suite '{suite_id}' not found.")
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Suite '{suite_id}' is malformed.") from exc
    if not isinstance(items, list):
        raise HTTPException(status_code=500, detail=f"Suite '{suite_id}' is malformed.")
    return items


def _build_item_prompt(suite_id: str, item: dict) -> str:
    if suite_id == "rag_faithfulness":
        return f"Context: {item['context']}\n\nQuestion: {item['question']}"
    return item["prompt"]


def _extract_code(response_text: str) -> str:
    """Pull a fenced Python code block out of a model response, falling back
    to the raw response text if no fence is present."""
    match = _CODE_FENCE_RE.search(response_text)
    return match.group(1) if match else response_text


async def _run_suite_for_model(
    slot: str,
    provider: str,
    model: str,
    api_key: str,
    suite_id: str,
    items: list[dict],
    consistency_runs: int,
    run_id: str,
) -> ModelResult:
    adapter = _ADAPTERS[provider]
    is_coding = suite_id == "coding"
    judge_metrics_for_suite = SUITE_JUDGE_METRICS.get(suite_id, ())

    all_latencies: list[float] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    response_previews: list[str] = []
    code_pass_count = 0
    code_total = 0
    metric_score_lists: dict[str, list[float]] = {m: [] for m in judge_metrics_for_suite}
    metric_reasoning: dict[str, str] = {}
    per_run_avg_scores: list[float] = []
    last_error: str | None = None
    any_success = False

    for run_number in range(consistency_runs):
        this_run_item_avgs: list[float] = []
        for item in items:
            prompt = _build_item_prompt(suite_id, item)
            response = await adapter.complete(prompt=prompt, api_key=api_key, model=model)
            all_latencies.append(response.latency_ms)

            if response.error is not None:
                last_error = response.error
                continue

            any_success = True
            total_input_tokens += response.input_tokens
            total_output_tokens += response.output_tokens
            total_cost += calculate_cost(model, response.input_tokens, response.output_tokens)

            if run_number == 0:
                response_previews.append(f"[{item['id']}] {response.text[:200]}")

            if is_coding:
                code = _extract_code(response.text)
                code_result = run_code_test(code, item["unit_tests"])
                code_total += 1
                if code_result.passed:
                    code_pass_count += 1
            elif judge_metrics_for_suite:
                judge_input = EvaluationInput(
                    question=item.get("question") or item.get("prompt", ""),
                    context=item.get("context") or "",
                    ai_response=response.text,
                    ground_truth=item.get("ground_truth"),
                )
                scores = await judge_all_metrics_async(judge_input, judge_metrics_for_suite)
                for name, result in scores.items():
                    metric_score_lists[name].append(result.score)
                    metric_reasoning[name] = result.reasoning
                if scores:
                    this_run_item_avgs.append(statistics.mean(r.score for r in scores.values()))

        if this_run_item_avgs:
            per_run_avg_scores.append(statistics.mean(this_run_item_avgs))

    await _publish(run_id, {"event": "model_done", "run_id": run_id, "slot": slot, "latency_ms": p50(all_latencies)})

    judge_scores = {
        name: JudgeScore(score=statistics.mean(scores), reasoning=metric_reasoning.get(name, ""))
        for name, scores in metric_score_lists.items()
        if scores
    }

    consistency: float | None = None
    if consistency_runs > 1 and len(per_run_avg_scores) > 1:
        consistency = max(0.0, 1 - statistics.pstdev(per_run_avg_scores))

    code_pass_rate = (code_pass_count / code_total) if code_total else None
    error = last_error if not any_success else None

    return ModelResult(
        provider=provider,
        model=model,
        response_text="\n".join(response_previews),
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        latency_ms=p50(all_latencies),
        cost_usd=total_cost,
        judge_scores=judge_scores,
        code_pass_rate=code_pass_rate,
        consistency=consistency,
        error=error,
    )


def _average_judge_score(result: ModelResult) -> float | None:
    if result.judge_scores:
        return statistics.mean(score.score for score in result.judge_scores.values())
    if result.code_pass_rate is not None:
        return result.code_pass_rate
    return None


def _rank_results(results: list[ModelResult]) -> tuple[list[ModelResult], list[str]]:
    """Order results best -> worst and assign competition-style ranks.

    Errored models always sort below scored ones; models with no score at all
    sit between (they beat errors but lose to any scored model). Equal
    (error-flag, aggregate) pairs share a rank: scores [0.9, 0.9, 0.5] rank
    [1, 1, 3]. The sort is stable, so submission order breaks exact ties.
    """
    for result in results:
        result.aggregate_score = _average_judge_score(result) if result.error is None else None

    def sort_key(result: ModelResult) -> tuple[bool, float]:
        score = result.aggregate_score if result.aggregate_score is not None else -1.0
        return (result.error is not None, -score)

    ordered = sorted(results, key=sort_key)

    rank = 0
    previous_key: tuple[bool, float | None] | None = None
    for position, result in enumerate(ordered, start=1):
        key = (result.error is not None, result.aggregate_score)
        if key != previous_key:
            rank = position
            previous_key = key
        result.rank = rank

    return ordered, [result.model for result in ordered]


def _task_count(suite_id: str | None, consistency_runs: int) -> int:
    """Number of individual model calls a run makes per model: suite items
    (1 in prompt mode) x consistency runs. Missing suite files degrade to 1
    item rather than failing a history read."""
    items = 1
    if suite_id is not None:
        try:
            items = len(_load_suite_items(suite_id))
        except HTTPException:
            items = 1
    return max(1, items) * max(1, consistency_runs)


def _enrich_results(results: list[ModelResult], suite_id: str | None, consistency_runs: int) -> None:
    """Fill the derived fields (tokens/sec, cost per task, per-1k projection).
    Derived at response time, never stored — legacy runs get them for free."""
    count = _task_count(suite_id, consistency_runs)
    for result in results:
        if result.error is not None:
            continue
        result.tokens_per_sec = tokens_per_sec(result.output_tokens, result.latency_ms, call_count=count)
        result.cost_per_task = cost_per_task(result.cost_usd, count)
        result.cost_per_1k_tasks = cost_per_1k_tasks(result.cost_usd, count)


@router.post("/compare", response_model=CompareResponse)
async def compare(request: Request, body: CompareRequest) -> CompareResponse:
    # One key per distinct provider, validated before any model call.
    api_keys = {
        provider: _extract_api_key(request, provider)
        for provider in {spec.provider for spec in body.models}
    }

    run_id = body.run_id or str(uuid.uuid4())
    await _publish(run_id, {"event": "started", "run_id": run_id})

    if body.suite_id is not None:
        items = _load_suite_items(body.suite_id)
        stored_prompt = None
        tasks = [
            _run_suite_for_model(
                str(index), spec.provider, spec.model, api_keys[spec.provider],
                body.suite_id, items, body.consistency_runs, run_id,
            )
            for index, spec in enumerate(body.models, start=1)
        ]
    else:
        stored_prompt = body.prompt or ""
        tasks = [
            _run_one_model(
                str(index), spec.provider, spec.model, stored_prompt,
                api_keys[spec.provider], run_id, body.consistency_runs,
            )
            for index, spec in enumerate(body.models, start=1)
        ]

    results = list(await asyncio.gather(*tasks))
    await _publish(run_id, {"event": "judge_done", "run_id": run_id})

    _enrich_results(results, body.suite_id, body.consistency_runs)
    ordered, ranking = _rank_results(results)
    created_at = datetime.now(UTC).isoformat()

    await arena_store.save_run(
        {
            "id": run_id,
            "suite_id": body.suite_id,
            "prompt": stored_prompt,
            "ranking": json.dumps(ranking),
            "consistency_runs": body.consistency_runs,
        }
    )

    # Persist in submission order so slot numbers stay stable.
    for index, result in enumerate(results, start=1):
        model_result_id = str(uuid.uuid4())
        await arena_store.save_model_result(
            {
                "id": model_result_id,
                "run_id": run_id,
                "slot": str(index),
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

    return CompareResponse(run_id=run_id, results=ordered, ranking=ranking, created_at=created_at)


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


def _summary_from_row(row: dict) -> RunSummary:
    if row["ranking"]:
        models = json.loads(row["ranking"])
        winner = models[0] if models else None
    else:  # legacy v1 row
        models = [m for m in (row["model_a"], row["model_b"]) if m]
        if row["winner"] == "model_a":
            winner = row["model_a"]
        elif row["winner"] == "model_b":
            winner = row["model_b"]
        else:
            winner = "tie" if row["winner"] == "tie" else None
    return RunSummary(
        run_id=row["id"], models=models, winner=winner, created_at=str(row["created_at"])
    )


@router.get("/runs", response_model=RunsListResponse)
async def list_runs(limit: int = 50, offset: int = 0) -> RunsListResponse:
    rows = await arena_store.get_all_runs(limit=limit, offset=offset)
    return RunsListResponse(total=len(rows), runs=[_summary_from_row(row) for row in rows])


async def _load_run_response(run_id: str) -> tuple[CompareResponse, dict]:
    """Rebuild a full CompareResponse from persisted rows (new or legacy)."""
    run = await arena_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    rows = await arena_store.get_model_results_for_run(run_id)
    if len(rows) < 2:
        raise HTTPException(status_code=500, detail="Run has incomplete data.")

    results: list[ModelResult] = []
    for row in rows:  # ORDER BY slot: works for "1".."4" and "model_a"/"model_b" alike
        scores = await arena_store.get_metric_scores_for_result(row["id"])
        judge_scores = {
            s["metric_name"]: JudgeScore(score=s["score"], reasoning=s["reasoning"] or "")
            for s in scores
        }
        results.append(
            ModelResult(
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
        )

    _enrich_results(results, run["suite_id"], run["consistency_runs"] or 1)
    ordered, ranking = _rank_results(results)
    return (
        CompareResponse(
            run_id=run["id"], results=ordered, ranking=ranking, created_at=str(run["created_at"])
        ),
        run,
    )


@router.get("/runs/{run_id}", response_model=CompareResponse)
async def get_run(run_id: str) -> CompareResponse:
    response, _ = await _load_run_response(run_id)
    return response


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
