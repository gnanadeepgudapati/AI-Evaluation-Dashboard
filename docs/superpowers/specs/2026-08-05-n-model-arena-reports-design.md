# N-Model Arena + Reports — Design Spec

**Date:** 2026-08-05
**Status:** Approved (user confirmed in-session; "proceed to build")
**Approach:** A — generalize the 2-model core in place (breaking API change; our React frontend is the only consumer)

## Goal

Expand the LLM Comparison Arena from exactly-2-model head-to-head into a one-stop comparison of **2–4 models** per run, scored on cost per task, speed, and quality, generating a **savable report** reachable from History, with deploy configs verified.

## Decisions (user-confirmed)

| Question | Decision |
|---|---|
| Models per comparison | 2–4 (duplicates allowed — same model twice is legal) |
| Winner semantics | Ranked leaderboard by `aggregate_score`; ties share a rank; `ranking[0]` is "the winner" |
| Cost metric | Total cost + `cost_per_task` (suite mode: cost ÷ item count) + `cost_per_1k_tasks` projection |
| Speed metric | p50 latency (existing) + `tokens_per_sec` (output_tokens ÷ latency seconds) |
| Report format | In-app report page with print CSS (browser Save-as-PDF) + Markdown export endpoint. No server-side PDF. |
| History scope | Per-run reports only; no cross-run aggregation this round |
| Deploy | Update configs if needed, verify `docker build` + container smoke test, document steps. No live deploy. |
| Data safety | **Hard requirement**: zero data loss; old runs remain fully readable |
| Git hygiene | Small commits pushed to `origin/main` at each milestone |

## 1. Data safety & migration

`model_results` and `metric_scores` need **no changes** (already one-row-per-model with a `slot` column). Only `runs` changes.

1. **Backup before migrating**: on startup, before any schema change, copy `arena.db` → `arena.db.backup-<timestamp>`.
2. **Versioned + idempotent**: `PRAGMA user_version` gates the migration; runs once, inside a single transaction; on failure the transaction rolls back and the app refuses to start with a clear error.
3. **Nothing deleted**: rebuild pattern (`CREATE runs_new` → copy all rows → rename). New table keeps `model_a/model_b/provider_a/provider_b/winner` as **nullable legacy columns** with values copied; adds `ranking TEXT` (JSON list of model names, best→worst). New runs fill `ranking`, leave legacy columns NULL.
4. **Legacy read path**: rows without `ranking` derive it — `winner="model_a"` → `[A, B]`; `"model_b"` → `[B, A]`; `"tie"`/NULL → stored order. Legacy slots `"model_a"/"model_b"` map to positions 1/2. New slots are `"1".."4"`.
5. **Proof**: a migration test builds a v1-schema DB with realistic rows, migrates, asserts row counts identical, every old run intact via `GET /runs/{id}`, and re-migration is a no-op.

## 2. API contract

```python
Provider = Literal["anthropic", "openai", "gemini"]

class ModelSpec(BaseModel):
    provider: Provider
    model: str

class CompareRequest(BaseModel):
    models: list[ModelSpec]        # min 2, max 4
    prompt: str | None = None      # XOR suite_id (unchanged)
    suite_id: str | None = None
    consistency_runs: int = 1      # 1–3 (unchanged)
    run_id: str | None = None

class ModelResult(BaseModel):
    # existing fields unchanged, plus:
    aggregate_score: float | None  # mean of judge metric scores; coding suite counts pass-rate as a metric
    rank: int | None               # 1 = best; equal scores share a rank; errored models rank last
    cost_per_task: float | None    # suite mode only: cost_usd / item_count
    cost_per_1k_tasks: float | None
    tokens_per_sec: float | None

class CompareResponse(BaseModel):
    run_id: str
    results: list[ModelResult]     # ordered by rank
    ranking: list[str]             # model names best→worst
    created_at: str
```

- **All new `ModelResult` fields are derived at read time, never stored**: `tokens_per_sec` from tokens+latency, `cost_per_task`/`cost_per_1k_tasks` from `cost_usd` + suite item count, `aggregate_score` from `metric_scores` rows, `rank` from the run's `ranking` order. This is why `model_results` needs no schema change and legacy runs get the new fields for free.
- `RunSummary` gains `models: list[str]`; `winner` = `ranking[0]`.
- BYOK headers unchanged: one `X-*-Key` per distinct provider; models sharing a provider share the key. Missing key → 400 naming the provider, before any model call.
- SSE: `model_a_done`/`model_b_done` → single `model_done` event carrying `slot`; `started`/`judge_done`/`complete` unchanged.
- Legacy `/evaluate`, `/evaluations` endpoints untouched.
- `GET /runs/{id}` returns the **new** shape for old runs too (2 results, derived ranking).

## 3. Backend compare flow

1. Validate request; collect one key per distinct provider.
2. `asyncio.gather` across all N models (suite mode: each model × all items; consistency: ×1–3). Each completion publishes `model_done`.
3. Groq judge scores all results, metrics in parallel (unchanged judge).
4. Per-model metrics: cost, cost_per_task, cost_per_1k_tasks, p50 latency, tokens_per_sec, code pass-rate, consistency.
5. `_rank_results(results) -> list[ModelResult]` replaces `_determine_winner`: sort by aggregate_score desc; errored last; equal scores share rank.
6. Persist one `runs` row (+`ranking` JSON), N `model_results` (slots `"1".."4"`), metric scores. Publish `complete`.

## 4. Report generation

Both renderings read the already-persisted run — nothing new stored; **existing runs get reports retroactively**.

**A. Report page** — React route `/report/:runId` fetching `GET /runs/{run_id}`:
- Verdict banner (winner + score line, rank medals)
- Leaderboard table: aggregate, per-metric scores, cost, cost/task, cost/1k tasks, p50, tokens/sec, consistency
- Recharts: grouped judge-metric bars; cost + latency comparisons
- Collapsible per-model responses; per-item breakdown in suite mode
- `@media print` CSS: hide nav/buttons, light theme, page breaks → clean browser Save-as-PDF
- Linked from ResultsPage and every HistoryPage row

**B. Markdown export** — `GET /runs/{run_id}/report.md` via new `api/report_md.py` (pure string templating, zero deps): verdict, leaderboard table, per-model details. "Download .md" button on the report page.

## 5. Frontend

- **ComparePage**: dynamic model list — 2 rows default, "+ Add model" to 4, remove to 2; one key input per distinct provider in the lineup.
- **ResultsPage**: leaderboard + N response columns (2×2 wrap at 4); "View report" link.
- **HistoryPage**: lists all models per run, crowns `ranking[0]`, "Open report" link. Legacy runs display identically.
- **Demo mode**: demo dataset becomes a 3-model example.

## 6. Error handling

- One model failing never kills the run (existing adapter contract): redacted error shown, ranks last, report notes it.
- All models failing: run persists with errors; report renders the failure state.
- Key redaction (ERR-003 fix) applies unchanged; e2e leak tests must stay green.

## 7. Testing

- Migration test on v1 fixture DB (the data-safety proof).
- Route tests at N=2/3/4; ranking + tie + errored-model ordering; cost-projection math; tokens_per_sec; `report.md` content assertions; SSE event sequence.
- All provider/judge calls mocked — no paid API calls in tests (existing rule).
- `pytest`, `ruff check .`, `mypy .` green before each push.

## 8. Deploy

- No new Python or npm dependencies expected → Docker/Render/Vercel configs likely unchanged; verify with full `docker build` + container smoke test (`/dashboard` served, `/compare` reachable).
- README updated for N-model + reports.
- Documented caveat: Render free tier disk is ephemeral — SQLite resets on redeploy; persistent disk add-on noted as the fix.

## Out of scope

- Cross-run aggregate leaderboard, server-side PDF, >4 models, auth on `/runs`, additional providers.
