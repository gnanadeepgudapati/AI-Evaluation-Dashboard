# N-Model Arena + Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize the 2-model comparison arena to 2–4 models with a ranked leaderboard, per-task cost + cost-per-1k-tasks projection, tokens/sec, a report page (print-to-PDF) + Markdown export, with a zero-data-loss `runs` table migration.

**Architecture:** The A/B-shaped `CompareRequest`/`CompareResponse` become list-shaped (`models: list[ModelSpec]`, `results: list[ModelResult]`, `ranking: list[str]`). `model_results`/`metric_scores` tables are untouched; only `runs` is rebuilt (versioned migration, backup first, legacy columns kept nullable). All new `ModelResult` fields are derived at read time from existing stored columns, so legacy runs get reports retroactively. Spec: `docs/superpowers/specs/2026-08-05-n-model-arena-reports-design.md`.

**Tech Stack:** FastAPI + Pydantic v2 + aiosqlite (backend), pytest + pytest-asyncio (asyncio_mode=auto), React 19 + TS + Vite + Tailwind v4 + Recharts (frontend).

## Global Constraints

- **Zero data loss** — migration backs up `arena.db` before touching it; legacy columns copied, never dropped; migration test proves round-trip.
- **No paid API calls in tests** — all provider/judge calls mocked (existing repo rule).
- **No new Python or npm dependencies.**
- Models per run: **min 2, max 4**; duplicates allowed.
- `consistency_runs` stays 1–3.
- BYOK headers unchanged: `X-Anthropic-Key`, `X-OpenAI-Key`, `X-Gemini-Key` — one per distinct provider.
- Legacy `/evaluate*` endpoints untouched.
- Ruff line-length 110, py311; `pytest`, `ruff check .`, `mypy .` must pass before every commit.
- Commit after every task; push to `origin/main` after Tasks 1, 5, 7, 12, 14 (milestones).
- Windows dev machine: activate venv via `.venv\Scripts\activate`; commands below assume repo root `C:\Users\Deepu gudapati\AI-Evaluation-Dashboard`.

---

### Task 1: Data-safe `runs` migration (v1 → v2)

**Files:**
- Create: `database/migrations.py`
- Modify: `database/arena_store.py` (schema + `initialize_arena_db` + `save_run`)
- Test: `tests/test_migrations.py`

**Interfaces:**
- Produces: `migrate_arena_db(db_path: str) -> None` (async), `ARENA_SCHEMA_VERSION = 2`.
- Produces: new `runs` schema: `id, suite_id, prompt, ranking TEXT, consistency_runs INTEGER, model_a, model_b, provider_a, provider_b, winner, created_at` — all legacy cols nullable.
- Produces: `arena_store.save_run(run: dict)` now expects keys `id, suite_id, prompt, ranking, consistency_runs` (ranking = JSON string).

- [ ] **Step 1: Write the failing migration test**

```python
# tests/test_migrations.py
# Proves the v1 -> v2 migration loses nothing: every row survives, a backup
# file is written first, and re-running the migration is a no-op.

import sqlite3
from pathlib import Path

import aiosqlite
import pytest

from database.migrations import ARENA_SCHEMA_VERSION, migrate_arena_db

V1_SCHEMA = """
CREATE TABLE runs (
    id            TEXT PRIMARY KEY,
    suite_id      TEXT,
    prompt        TEXT,
    model_a       TEXT NOT NULL,
    model_b       TEXT NOT NULL,
    provider_a    TEXT NOT NULL,
    provider_b    TEXT NOT NULL,
    winner        TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE model_results (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    slot            TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    provider        TEXT NOT NULL,
    response_text   TEXT,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    latency_ms      REAL,
    cost_usd        REAL,
    code_pass_rate  REAL,
    consistency     REAL,
    error           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE metric_scores (
    id               TEXT PRIMARY KEY,
    model_result_id  TEXT NOT NULL REFERENCES model_results(id),
    metric_name      TEXT NOT NULL,
    score            REAL NOT NULL,
    reasoning        TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _build_v1_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(V1_SCHEMA)
    conn.execute(
        "INSERT INTO runs (id, suite_id, prompt, model_a, model_b, provider_a, provider_b, winner) "
        "VALUES ('run-1', NULL, 'What is 2+2?', 'claude-3-5-haiku-20241022', 'gpt-4o-mini', "
        "'anthropic', 'openai', 'model_b')"
    )
    conn.execute(
        "INSERT INTO runs (id, suite_id, prompt, model_a, model_b, provider_a, provider_b, winner) "
        "VALUES ('run-2', 'reasoning', NULL, 'gpt-4o', 'gemini-1.5-pro', 'openai', 'gemini', 'tie')"
    )
    conn.execute(
        "INSERT INTO model_results (id, run_id, slot, model_name, provider, response_text, "
        "input_tokens, output_tokens, latency_ms, cost_usd, code_pass_rate, consistency, error) "
        "VALUES ('mr-1', 'run-1', 'model_a', 'claude-3-5-haiku-20241022', 'anthropic', '4', "
        "10, 5, 900.0, 0.0001, NULL, NULL, NULL)"
    )
    conn.execute(
        "INSERT INTO metric_scores (id, model_result_id, metric_name, score, reasoning) "
        "VALUES ('ms-1', 'mr-1', 'correctness', 0.9, 'right answer')"
    )
    conn.commit()
    conn.close()


async def test_migration_preserves_every_row_and_writes_backup(tmp_path):
    db_path = str(tmp_path / "arena.db")
    _build_v1_db(db_path)

    await migrate_arena_db(db_path)

    backups = list(tmp_path.glob("arena.db.backup-*"))
    assert len(backups) == 1, "backup file must be written before migrating"

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("PRAGMA user_version")
        (version,) = await cursor.fetchone()
        assert version == ARENA_SCHEMA_VERSION

        cursor = await db.execute("SELECT * FROM runs ORDER BY id")
        rows = [dict(r) for r in await cursor.fetchall()]
        assert len(rows) == 2
        assert rows[0]["model_a"] == "claude-3-5-haiku-20241022"
        assert rows[0]["winner"] == "model_b"
        assert rows[0]["ranking"] is None          # legacy rows have no ranking
        assert rows[0]["consistency_runs"] is None
        assert rows[1]["suite_id"] == "reasoning"

        cursor = await db.execute("SELECT COUNT(*) FROM model_results")
        assert (await cursor.fetchone())[0] == 1
        cursor = await db.execute("SELECT COUNT(*) FROM metric_scores")
        assert (await cursor.fetchone())[0] == 1


async def test_migration_is_idempotent(tmp_path):
    db_path = str(tmp_path / "arena.db")
    _build_v1_db(db_path)

    await migrate_arena_db(db_path)
    await migrate_arena_db(db_path)  # second run must be a no-op

    backups = list(tmp_path.glob("arena.db.backup-*"))
    assert len(backups) == 1, "no second backup on a no-op re-run"

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM runs")
        assert (await cursor.fetchone())[0] == 2


async def test_migration_noop_on_missing_file(tmp_path):
    await migrate_arena_db(str(tmp_path / "does_not_exist.db"))  # must not raise
    assert not Path(tmp_path / "does_not_exist.db").exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_migrations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'database.migrations'`

- [ ] **Step 3: Implement `database/migrations.py`**

```python
# migrations.py
# Versioned, data-safe schema migrations for arena.db.
#
# Rules:
#   - A timestamped backup copy of the DB file is written BEFORE any change.
#   - The migration runs in one transaction; on failure it rolls back and raises.
#   - Nothing is lost: the v1 -> v2 rebuild copies every legacy column
#     (model_a/model_b/provider_a/provider_b/winner) into the new table as
#     nullable columns, and the pre-migration file survives as the backup.
#   - PRAGMA user_version tracks the schema version (0 = pre-versioning v1).

import shutil
from datetime import datetime
from pathlib import Path

import aiosqlite

ARENA_SCHEMA_VERSION = 2

_RUNS_V2_COLUMNS = """
    id               TEXT PRIMARY KEY,
    suite_id         TEXT,
    prompt           TEXT,
    ranking          TEXT,
    consistency_runs INTEGER,
    model_a          TEXT,
    model_b          TEXT,
    provider_a       TEXT,
    provider_b       TEXT,
    winner           TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
"""


def _backup(db_path: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{db_path}.backup-{stamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path


async def migrate_arena_db(db_path: str) -> None:
    """Bring an existing arena.db up to ARENA_SCHEMA_VERSION.

    No-op when the file doesn't exist (fresh install — initialize_arena_db
    creates the v2 schema directly) or when the DB is already migrated.
    """
    if not Path(db_path).exists():
        return

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("PRAGMA user_version")
        (version,) = await cursor.fetchone()
        if version >= ARENA_SCHEMA_VERSION:
            return

        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
        )
        if await cursor.fetchone() is None:
            return  # empty file: schema creation will stamp the version

        _backup(db_path)

        try:
            await db.execute(f"CREATE TABLE runs_new ({_RUNS_V2_COLUMNS})")
            await db.execute(
                """
                INSERT INTO runs_new
                    (id, suite_id, prompt, ranking, consistency_runs,
                     model_a, model_b, provider_a, provider_b, winner, created_at)
                SELECT id, suite_id, prompt, NULL, NULL,
                       model_a, model_b, provider_a, provider_b, winner, created_at
                FROM runs
                """
            )
            await db.execute("DROP TABLE runs")
            await db.execute("ALTER TABLE runs_new RENAME TO runs")
            await db.execute(f"PRAGMA user_version = {ARENA_SCHEMA_VERSION}")
            await db.commit()
        except Exception:
            await db.rollback()
            raise
```

- [ ] **Step 4: Update `database/arena_store.py`**

Replace the `runs` block inside `_SCHEMA` (keep `model_results` and `metric_scores` exactly as they are):

```python
_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id               TEXT PRIMARY KEY,
    suite_id         TEXT,
    prompt           TEXT,
    ranking          TEXT,
    consistency_runs INTEGER,
    model_a          TEXT,
    model_b          TEXT,
    provider_a       TEXT,
    provider_b       TEXT,
    winner           TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
... (model_results and metric_scores unchanged) ...
"""
```

Replace `initialize_arena_db` and `save_run`:

```python
from database.migrations import ARENA_SCHEMA_VERSION, migrate_arena_db


async def initialize_arena_db() -> None:
    """Migrate an existing DB if needed, then create any missing tables.
    Safe to call repeatedly."""
    await migrate_arena_db(DB_PATH)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.execute(f"PRAGMA user_version = {ARENA_SCHEMA_VERSION}")
        await db.commit()


async def save_run(run: dict) -> None:
    """Persist an N-model run. Legacy columns (model_a/... / winner) stay NULL
    on new rows — the model lineup lives in model_results, ranking in `ranking`."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO runs (id, suite_id, prompt, ranking, consistency_runs)
            VALUES (:id, :suite_id, :prompt, :ranking, :consistency_runs)
            """,
            run,
        )
        await db.commit()
```

- [ ] **Step 5: Run migration tests**

Run: `python -m pytest tests/test_migrations.py -v`
Expected: 3 PASS. (`tests/test_compare_routes.py` will FAIL until Task 5 — that's expected; don't run the full suite green-gate until Task 5's final step.)

- [ ] **Step 6: Commit and push**

```bash
git add database/migrations.py database/arena_store.py tests/test_migrations.py
git commit -m "feat: versioned data-safe runs-table migration (v1->v2, backup + rebuild)"
git push origin main
```

---

### Task 2: N-model API contracts

**Files:**
- Modify: `api/models.py` (full rewrite of `CompareRequest`/`CompareResponse`/`ModelResult`/`RunSummary`; add `ModelSpec`)
- Test: `tests/test_models_contract.py` (new)

**Interfaces:**
- Produces (used by every later task):
  - `ModelSpec(provider: Provider, model: str)`
  - `CompareRequest(models: list[ModelSpec], prompt, suite_id, consistency_runs, run_id)` — validates 2–4 models, prompt XOR suite, runs in {1,2,3}
  - `ModelResult` gains `aggregate_score: float | None`, `rank: int | None`, `cost_per_task: float | None`, `cost_per_1k_tasks: float | None`, `tokens_per_sec: float | None` (all default `None`)
  - `CompareResponse(run_id, results: list[ModelResult], ranking: list[str], created_at)`
  - `RunSummary(run_id, models: list[str], winner: str | None, created_at)`

- [ ] **Step 1: Write the failing contract tests**

```python
# tests/test_models_contract.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_models_contract.py -v`
Expected: FAIL — `ImportError: cannot import name 'ModelSpec'`

- [ ] **Step 3: Rewrite `api/models.py` contracts**

Keep `Provider`, `JudgeScore`, `RunsListResponse`, `SuiteMetadata` as-is. Replace the rest:

```python
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


class RunSummary(BaseModel):
    run_id: str
    models: list[str]
    winner: str | None           # model NAME (ranking[0]), or "tie" on legacy ties
    created_at: str
```

- [ ] **Step 4: Run contract tests**

Run: `python -m pytest tests/test_models_contract.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add api/models.py tests/test_models_contract.py
git commit -m "feat: N-model API contracts (ModelSpec, list-shaped request/response, derived fields)"
```

---

### Task 3: Derived-metric helpers (cost per task, projection, tokens/sec)

**Files:**
- Modify: `metrics/cost.py`, `metrics/latency.py`
- Test: `tests/test_metrics.py` (append)

**Interfaces:**
- Produces: `cost.cost_per_task(total_cost_usd: float, task_count: int) -> float | None`
- Produces: `cost.cost_per_1k_tasks(total_cost_usd: float, task_count: int) -> float | None`
- Produces: `latency.tokens_per_sec(output_tokens: int, latency_ms: float, call_count: int = 1) -> float | None`

- [ ] **Step 1: Write the failing tests (append to `tests/test_metrics.py`)**

```python
from metrics.cost import cost_per_1k_tasks, cost_per_task
from metrics.latency import tokens_per_sec


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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_metrics.py -v -k "cost_per or tokens_per"`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement**

Append to `metrics/cost.py`:

```python
def cost_per_task(total_cost_usd: float, task_count: int) -> float | None:
    """Average cost of one task (one model call on one item)."""
    if task_count <= 0:
        return None
    return total_cost_usd / task_count


def cost_per_1k_tasks(total_cost_usd: float, task_count: int) -> float | None:
    """Projected spend for 1,000 tasks at the observed per-task cost."""
    per_task = cost_per_task(total_cost_usd, task_count)
    return None if per_task is None else per_task * 1000.0
```

Append to `metrics/latency.py`:

```python
def tokens_per_sec(output_tokens: int, latency_ms: float, call_count: int = 1) -> float | None:
    """Approximate generation throughput: average output tokens per call
    divided by the p50 call latency. An estimate — token totals are summed
    across calls while latency is a percentile, not a sum."""
    if latency_ms <= 0 or call_count <= 0:
        return None
    return (output_tokens / call_count) / (latency_ms / 1000.0)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: all PASS (old + 6 new)

- [ ] **Step 5: Commit**

```bash
git add metrics/cost.py metrics/latency.py tests/test_metrics.py
git commit -m "feat: cost-per-task, cost-per-1k projection, tokens/sec helpers"
```

---

### Task 4: Ranking + enrichment (pure functions in `compare_routes`)

**Files:**
- Modify: `api/compare_routes.py` (add `_rank_results`, `_enrich_results`, `_task_count`; delete `_determine_winner`)
- Test: `tests/test_ranking.py` (new)

**Interfaces:**
- Consumes: `ModelResult` (Task 2), helpers (Task 3), existing `_average_judge_score`, `_load_suite_items`.
- Produces: `_rank_results(results: list[ModelResult]) -> tuple[list[ModelResult], list[str]]` — mutates `aggregate_score`/`rank` in place, returns (ordered best→worst, ranking names). Errored models always last; equal aggregates share a rank (competition ranking); stable for ties.
- Produces: `_enrich_results(results: list[ModelResult], suite_id: str | None, consistency_runs: int) -> None` — fills `tokens_per_sec`, `cost_per_task`, `cost_per_1k_tasks` on non-errored results.
- Produces: `_task_count(suite_id: str | None, consistency_runs: int) -> int` — suite item count (1 in prompt mode) × consistency_runs; falls back to 1 × runs if the suite file is missing.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ranking.py
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_ranking.py -v`
Expected: FAIL — ImportError (`_rank_results` not defined)

- [ ] **Step 3: Implement in `api/compare_routes.py`**

Add imports `from metrics.cost import calculate_cost, cost_per_1k_tasks, cost_per_task` and `from metrics.latency import p50, tokens_per_sec` (extend the existing import lines). Delete `_determine_winner` entirely. Add after `_average_judge_score`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_ranking.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add api/compare_routes.py tests/test_ranking.py
git commit -m "feat: N-model ranking and derived-metric enrichment"
```

---

### Task 5: Rewrite `POST /compare` for N models (+ SSE `model_done`)

**Files:**
- Modify: `api/compare_routes.py` (the `compare` endpoint; `_run_one_model`/`_run_suite_for_model` publish events)
- Modify: `tests/test_compare_routes.py` (payloads + assertions)

**Interfaces:**
- Consumes: `CompareRequest.models` (Task 2), `_rank_results`/`_enrich_results` (Task 4), `arena_store.save_run` with `ranking`/`consistency_runs` keys (Task 1).
- Produces: `POST /compare` accepting `{"models": [{"provider": ..., "model": ...}, ...], ...}`; response `{run_id, results, ranking, created_at}`. SSE event stream: `started` → N× `model_done` (payload has `slot`) → `judge_done` → `complete`. Persists slots `"1".."4"` in submission order.

- [ ] **Step 1: Update the SSE publish in both runner helpers**

In `_run_one_model` (line ~111) and `_run_suite_for_model` (line ~243), replace
`{"event": f"{slot}_done", ...}` with:

```python
await _publish(run_id, {"event": "model_done", "run_id": run_id, "slot": slot, "latency_ms": ...})
```

(keep each call's existing `latency_ms` expression). In `stream_run`'s `event_generator`, no change — it forwards whatever event name was published.

- [ ] **Step 2: Rewrite the `compare` endpoint**

```python
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
```

Note: `GET /runs` and `GET /runs/{id}` are now broken (they read `model_a` etc.) — Task 6 fixes them. To keep this task's test run green, Task 5 and Task 6 share one final verification; run only the compare tests here.

- [ ] **Step 3: Update `tests/test_compare_routes.py` to the new shape**

Replace `VALID_PAYLOAD`:

```python
VALID_PAYLOAD = {
    "models": [
        {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
        {"provider": "openai", "model": "gpt-4o-mini"},
    ],
    "prompt": "Explain recursion with a Python example",
}
```

Update every test that referenced `data["model_a"]` / `data["model_b"]` / `data["winner"]` to the list shape. Specifically:
- `test_compare_success_returns_full_response`: assert `len(data["results"]) == 2`, `data["ranking"]` is a 2-item list of the payload's model names, `data["results"][0]["rank"] == 1`, `data["results"][0]["response_text"] == "fake response"`, judge-score keys unchanged, and new derived fields present: `data["results"][0]["tokens_per_sec"] is not None`, `data["results"][0]["cost_per_task"] is not None`.
- `test_compare_consistency_runs_computes_consistency_score`: `data["results"][0]["consistency"] == 1.0`.
- `test_provider_auth_error_never_leaks_key_over_http` (redaction e2e): replace `history.json()["model_b"]["error"]` with
  `next(r["error"] for r in history.json()["results"] if r["error"])` and assert `"[REDACTED]"` in it. Keep both `byok_key not in resp.text` assertions exactly as they are.
- Any suite-mode / errored-model tests: same list-shape translation (find them with `grep -n "model_a\|model_b\|winner" tests/test_compare_routes.py` and convert each).

Add two new tests:

```python
def test_compare_three_models_ranks_all(client, monkeypatch):
    monkeypatch.setitem(compare_routes._ADAPTERS, "gemini", FakeAdapter(text="third response"))
    payload = {
        "models": [
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-1.5-flash"},
        ],
        "prompt": "hello",
    }
    headers = {**VALID_HEADERS, "X-Gemini-Key": "AIza" + "S" * 35}
    resp = client.post("/compare", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 3
    assert len(data["ranking"]) == 3
    assert sorted(r["rank"] for r in data["results"]) == [1, 1, 1]  # identical fake scores tie


def test_compare_missing_key_for_any_provider_400s_before_calls(client):
    payload = {
        "models": [
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "gemini", "model": "gemini-1.5-flash"},
        ],
        "prompt": "hello",
    }
    resp = client.post("/compare", json=payload, headers={"X-Anthropic-Key": "sk-ant-test"})
    assert resp.status_code == 400
    assert "gemini" in resp.json()["detail"]
```

- [ ] **Step 4: Run compare tests only**

Run: `python -m pytest tests/test_compare_routes.py -v -k "compare"`
Expected: all `compare`-named tests PASS. (`/runs` read-path tests still fail until Task 6.)

- [ ] **Step 5: Commit and push**

```bash
git add api/compare_routes.py tests/test_compare_routes.py
git commit -m "feat: POST /compare accepts 2-4 models, ranked results, model_done SSE"
git push origin main
```

---

### Task 6: Read path — `GET /runs` and `GET /runs/{id}` for new + legacy rows

**Files:**
- Modify: `api/compare_routes.py` (`list_runs`, `get_run`; extract `_load_run_response`)
- Test: `tests/test_compare_routes.py` (history tests + legacy-run test)

**Interfaces:**
- Consumes: v2 `runs` columns (Task 1), `_rank_results`/`_enrich_results` (Task 4).
- Produces: `_load_run_response(run_id: str) -> tuple[CompareResponse, dict]` — the run dict is the raw `runs` row (Task 7 needs `suite_id`/`prompt` from it). Legacy slots `"model_a"/"model_b"` and new slots `"1".."4"` both order correctly via the existing `ORDER BY slot`.

- [ ] **Step 1: Write the failing legacy-compat test (append to `tests/test_compare_routes.py`)**

```python
async def _seed_legacy_run() -> None:
    """Insert a pre-migration-shaped run: legacy runs columns filled,
    ranking NULL, slots 'model_a'/'model_b'."""
    await arena_store.save_model_result({
            "id": "legacy-mr-a", "run_id": "legacy-run", "slot": "model_a",
            "model_name": "claude-3-5-haiku-20241022", "provider": "anthropic",
            "response_text": "old answer A", "input_tokens": 10, "output_tokens": 20,
            "latency_ms": 900.0, "cost_usd": 0.001, "code_pass_rate": None,
            "consistency": None, "error": None,
        })
        await arena_store.save_model_result({
            "id": "legacy-mr-b", "run_id": "legacy-run", "slot": "model_b",
            "model_name": "gpt-4o-mini", "provider": "openai",
            "response_text": "old answer B", "input_tokens": 10, "output_tokens": 20,
            "latency_ms": 800.0, "cost_usd": 0.002, "code_pass_rate": None,
            "consistency": None, "error": None,
        })
        await arena_store.save_metric_score({
            "id": "legacy-ms-1", "model_result_id": "legacy-mr-a",
            "metric_name": "correctness", "score": 0.9, "reasoning": "good",
        })
        await arena_store.save_metric_score({
            "id": "legacy-ms-2", "model_result_id": "legacy-mr-b",
            "metric_name": "correctness", "score": 0.5, "reasoning": "meh",
        })
    # Raw insert mimicking a migrated v1 row: legacy cols set, ranking NULL.
    import aiosqlite
    async with aiosqlite.connect(arena_store.DB_PATH) as db:
        await db.execute(
            "INSERT INTO runs (id, suite_id, prompt, model_a, model_b, provider_a, provider_b, winner) "
            "VALUES ('legacy-run', NULL, 'old prompt', 'claude-3-5-haiku-20241022', 'gpt-4o-mini', "
            "'anthropic', 'openai', 'model_a')"
        )
        await db.commit()


def test_legacy_two_model_run_still_readable(client):
    """A pre-migration run (legacy columns + model_a/model_b slots, no ranking)
    must render through the new list-shaped API. The client fixture has already
    initialized/migrated the tmp DB by the time the test body runs, so seeding
    with asyncio.run() here is safe."""
    import asyncio
    asyncio.run(_seed_legacy_run())

    detail = client.get("/runs/legacy-run")
    assert detail.status_code == 200
    data = detail.json()
    assert len(data["results"]) == 2
    assert data["ranking"][0] == "claude-3-5-haiku-20241022"  # 0.9 beats 0.5
    assert data["results"][0]["rank"] == 1
    assert data["results"][0]["cost_per_task"] is not None    # derived retroactively

    listing = client.get("/runs")
    assert listing.status_code == 200
    row = next(r for r in listing.json()["runs"] if r["run_id"] == "legacy-run")
    assert row["models"] == ["claude-3-5-haiku-20241022", "gpt-4o-mini"]
    assert row["winner"] == "claude-3-5-haiku-20241022"
```

(Define `_seed_legacy_run()` as a module-level `async def` containing the four `save_*` calls and the raw `INSERT` from the first snippet.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_compare_routes.py -v -k "legacy or history or runs"`
Expected: FAIL (read path still selects `model_a`)

- [ ] **Step 3: Rewrite the read path in `api/compare_routes.py`**

```python
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
```

(Ranking is *recomputed* from stored judge scores rather than read from the `ranking` column — same `_rank_results` both ways guarantees write/read agreement, and it's what makes legacy rows work. The stored JSON serves `GET /runs` summaries without N+1 queries.)

- [ ] **Step 4: Run the whole backend suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS — this is the gate for Tasks 1–6 together.

- [ ] **Step 5: Lint, type-check, commit**

Run: `ruff check . && mypy .` — both clean.

```bash
git add api/compare_routes.py tests/test_compare_routes.py
git commit -m "feat: list-shaped run read path with legacy v1 row support"
```

---

### Task 7: Markdown report endpoint

**Files:**
- Create: `api/report_md.py`
- Modify: `api/compare_routes.py` (new route)
- Test: `tests/test_report_md.py` (new)

**Interfaces:**
- Consumes: `_load_run_response` (Task 6).
- Produces: `render_markdown_report(response: CompareResponse, suite_id: str | None, prompt: str | None, consistency_runs: int) -> str`; route `GET /runs/{run_id}/report.md` returning `text/markdown` with `Content-Disposition: attachment`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_report_md.py
from api.models import CompareResponse, JudgeScore, ModelResult
from api.report_md import render_markdown_report


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


def test_report_md_endpoint(client):
    """Endpoint variant — reuses the client fixture from test_compare_routes."""
    from tests.test_compare_routes import VALID_HEADERS, VALID_PAYLOAD

    run = client.post("/compare", json=VALID_PAYLOAD, headers=VALID_HEADERS).json()
    resp = client.get(f"/runs/{run['run_id']}/report.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "attachment" in resp.headers["content-disposition"]
    assert "# LLM Comparison Report" in resp.text
```

For the endpoint test, import the `client` fixture by adding at the top of `tests/test_report_md.py`:

```python
from tests.test_compare_routes import client  # noqa: F401  (pytest fixture reuse)
import pytest
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_report_md.py -v`
Expected: FAIL — no module `api.report_md`

- [ ] **Step 3: Implement `api/report_md.py`**

```python
# report_md.py
# Renders a persisted comparison run as a portable Markdown report.
# Pure string templating — no dependencies, no I/O.

from api.models import CompareResponse, ModelResult


def _fmt(value: float | None, spec: str = ".4f", suffix: str = "") -> str:
    return "—" if value is None else f"{value:{spec}}{suffix}"


def _usd(value: float | None) -> str:
    return "—" if value is None else f"${value:.4f}"


def _leaderboard_row(result: ModelResult) -> str:
    if result.error is not None:
        return (
            f"| {result.rank} | {result.model} | {result.provider} | failed | — | — | — | — | — | — |"
        )
    return (
        f"| {result.rank} | {result.model} | {result.provider} "
        f"| {_fmt(result.aggregate_score, '.2f')} | {_usd(result.cost_usd)} "
        f"| {_usd(result.cost_per_task)} | {_usd(result.cost_per_1k_tasks)} "
        f"| {_fmt(result.latency_ms, '.0f', ' ms')} | {_fmt(result.tokens_per_sec, '.1f')} "
        f"| {_fmt(result.consistency, '.2f')} |"
    )


def render_markdown_report(
    response: CompareResponse,
    suite_id: str | None,
    prompt: str | None,
    consistency_runs: int,
) -> str:
    mode = f"Suite `{suite_id}`" if suite_id else "Custom prompt"
    winner = response.ranking[0] if response.ranking else "—"
    lines = [
        "# LLM Comparison Report",
        "",
        f"**Run:** `{response.run_id}` · **Date:** {response.created_at} · "
        f"**Mode:** {mode} · **Consistency runs:** {consistency_runs}",
        "",
        f"**Winner:** {winner}",
        "",
        "## Leaderboard",
        "",
        "| Rank | Model | Provider | Aggregate | Cost | Cost/task | Cost/1k tasks "
        "| p50 latency | Tokens/sec | Consistency |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    lines += [_leaderboard_row(result) for result in response.results]

    metric_names = sorted({m for r in response.results for m in r.judge_scores})
    if metric_names:
        lines += ["", "## Judge metric scores", ""]
        lines.append("| Model | " + " | ".join(metric_names) + " |")
        lines.append("|---|" + "---|" * len(metric_names))
        for result in response.results:
            cells = [
                _fmt(result.judge_scores[m].score, ".2f") if m in result.judge_scores else "—"
                for m in metric_names
            ]
            lines.append(f"| {result.model} | " + " | ".join(cells) + " |")

    if prompt:
        lines += ["", "## Prompt", "", "```", prompt, "```"]

    lines += ["", "## Responses", ""]
    for result in response.results:
        lines.append(f"### {result.rank}. {result.model} ({result.provider})")
        lines.append("")
        if result.error is not None:
            lines.append(f"**This model failed:** `{result.error}`")
        else:
            lines += ["```", result.response_text or "(empty response)", "```"]
        lines.append("")

    lines.append("---")
    lines.append("*Generated by LLM Comparison Arena.*")
    return "\n".join(lines)
```

- [ ] **Step 4: Add the route in `api/compare_routes.py`**

Add `from fastapi import Response` to imports (extend the existing `fastapi` import line) and `from api.report_md import render_markdown_report`. **Place this route ABOVE `get_run`** (FastAPI matches in registration order; `/runs/{run_id}/report.md` must not be captured by `/runs/{run_id}` — distinct path shapes, but explicit ordering removes doubt):

```python
@router.get("/runs/{run_id}/report.md")
async def get_run_report_md(run_id: str) -> Response:
    response, run = await _load_run_response(run_id)
    markdown = render_markdown_report(
        response,
        suite_id=run["suite_id"],
        prompt=run["prompt"],
        consistency_runs=run["consistency_runs"] or 1,
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="report-{run_id[:8]}.md"'},
    )
```

- [ ] **Step 5: Run tests, lint, commit, push**

Run: `python -m pytest tests/ -v && ruff check . && mypy .`
Expected: ALL PASS / clean.

```bash
git add api/report_md.py api/compare_routes.py tests/test_report_md.py
git commit -m "feat: GET /runs/{id}/report.md markdown report export"
git push origin main
```

---

### Task 8: Frontend foundations — types, API client, SSE hook, ProgressBar

**Files:**
- Modify: `frontend-src/src/types/index.ts`, `frontend-src/src/lib/api.ts`, `frontend-src/src/hooks/useEventSource.ts`, `frontend-src/src/components/ProgressBar.tsx`, `frontend-src/src/context/ArenaContext.tsx` (no change needed — verify only)

**Interfaces:**
- Produces (consumed by Tasks 9–12): `ModelSpec`, list-shaped `CompareRequest`/`CompareResponse`, `RunSummary.models`, `reportMdUrl(runId)`, `useEventSource(runId): ProgressState` where `ProgressState = { stage: 'idle'|'started'|'running'|'judge_done'|'complete'; modelsDone: number }`, `ProgressBar({ state, totalModels })`.

- [ ] **Step 1: Update `types/index.ts`**

Replace `ModelResult`, `CompareRequest`, `CompareResponse`, `RunSummary`; delete `Winner`; add `ModelSpec`. Keep `Provider`, `JudgeScore`, `RunsListResponse`, `SuiteMetadata`, `ApiKeys`, `MODELS_BY_PROVIDER`, `JUDGE_METRIC_LABELS`:

```ts
export interface ModelSpec {
  provider: Provider
  model: string
}

export interface ModelResult {
  model: string
  provider: Provider
  response_text: string
  input_tokens: number
  output_tokens: number
  latency_ms: number
  cost_usd: number
  judge_scores: Record<string, JudgeScore>
  code_pass_rate: number | null
  consistency: number | null
  error: string | null
  aggregate_score: number | null
  rank: number | null
  cost_per_task: number | null
  cost_per_1k_tasks: number | null
  tokens_per_sec: number | null
}

export interface CompareRequest {
  models: ModelSpec[]
  prompt?: string
  suite_id?: string
  consistency_runs?: number
  run_id?: string
}

export interface CompareResponse {
  run_id: string
  results: ModelResult[]   // ordered best -> worst
  ranking: string[]        // model names best -> worst
  created_at: string
}

export interface RunSummary {
  run_id: string
  models: string[]
  winner: string | null
  created_at: string
}

export const MODEL_SERIES_COLORS = ['#38bdf8', '#a78bfa', '#fb923c', '#4ade80']
```

- [ ] **Step 2: Update `lib/api.ts`**

Add after `streamUrl`:

```ts
export function reportMdUrl(runId: string): string {
  return `${API_BASE}/runs/${runId}/report.md`
}
```

(No other changes — `postCompare` already sends whatever `CompareRequest` is.)

- [ ] **Step 3: Rewrite `hooks/useEventSource.ts`**

```ts
// Wraps the native EventSource API for /stream/{run_id}. The caller opens the
// stream with a client-generated run_id BEFORE posting /compare (same run_id
// in the body) so the server publishes to a queue this stream already reads.
//
// Event sequence: started -> N x model_done (payload carries `slot`) ->
// judge_done -> complete.

import { useEffect, useRef, useState } from 'react'
import { streamUrl } from '../lib/api'

export interface ProgressState {
  stage: 'idle' | 'started' | 'running' | 'judge_done' | 'complete'
  modelsDone: number
}

const IDLE: ProgressState = { stage: 'idle', modelsDone: 0 }

export function useEventSource(runId: string | null): ProgressState {
  const [state, setState] = useState<ProgressState>(IDLE)
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!runId) return

    setState(IDLE)
    const source = new EventSource(streamUrl(runId))
    sourceRef.current = source

    source.addEventListener('started', () => setState({ stage: 'started', modelsDone: 0 }))
    source.addEventListener('model_done', () =>
      setState((prev) => ({ stage: 'running', modelsDone: prev.modelsDone + 1 })),
    )
    source.addEventListener('judge_done', () =>
      setState((prev) => ({ ...prev, stage: 'judge_done' })),
    )
    source.addEventListener('complete', () => {
      setState((prev) => ({ ...prev, stage: 'complete' }))
      source.close()
    })

    source.onerror = () => {
      // Connection closed by server (timeout or complete) — nothing to do.
    }

    return () => {
      source.close()
      sourceRef.current = null
    }
  }, [runId])

  return state
}
```

- [ ] **Step 4: Rewrite `components/ProgressBar.tsx`**

```tsx
import type { ProgressState } from '../hooks/useEventSource'

export default function ProgressBar({
  state,
  totalModels,
}: {
  state: ProgressState
  totalModels: number
}) {
  // started (1) + one segment per model + judged (1) + complete (1)
  const totalSegments = totalModels + 3
  const filled =
    state.stage === 'idle'
      ? 0
      : state.stage === 'started'
        ? 1
        : state.stage === 'running'
          ? 1 + state.modelsDone
          : state.stage === 'judge_done'
            ? totalSegments - 1
            : totalSegments

  const label =
    state.stage === 'idle'
      ? 'Waiting to start…'
      : state.stage === 'started'
        ? 'Started'
        : state.stage === 'running'
          ? `Models responded: ${state.modelsDone}/${totalModels}`
          : state.stage === 'judge_done'
            ? 'Judged'
            : 'Complete'

  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-2 overflow-hidden rounded-full bg-surface">
        {Array.from({ length: totalSegments }, (_, i) => (
          <div
            key={i}
            className={`flex-1 border-r border-bg last:border-r-0 transition-colors ${
              i < filled ? 'bg-accent-blue' : 'bg-surface'
            }`}
          />
        ))}
      </div>
      <div className="font-mono-ui text-xs text-muted">{label}</div>
    </div>
  )
}
```

- [ ] **Step 5: Type-check compile (expect known breakage)**

Run: `cd frontend-src && npx tsc --noEmit`
Expected: errors ONLY in `ComparePage.tsx`, `ResultsPage.tsx`, `HistoryPage.tsx`, `ModelCard.tsx`, `RadarMetrics.tsx`, `CostLatencyCharts.tsx`, `WinnerBanner.tsx` (fixed in Tasks 9–11). No errors in the four files this task touched.

- [ ] **Step 6: Commit**

```bash
git add frontend-src/src/types/index.ts frontend-src/src/lib/api.ts frontend-src/src/hooks/useEventSource.ts frontend-src/src/components/ProgressBar.tsx
git commit -m "feat(frontend): N-model types, report URL, model_done SSE progress"
```

---

### Task 9: ComparePage — dynamic 2–4 model lineup

**Files:**
- Modify: `frontend-src/src/pages/ComparePage.tsx`

**Interfaces:**
- Consumes: `ModelSpec`, list `CompareRequest` (Task 8), `ProgressBar({state, totalModels})`.

- [ ] **Step 1: Rewrite lineup state + submit**

Replace the four `providerA/modelA/providerB/modelB` states with:

```tsx
const [lineup, setLineup] = useState<ModelSpec[]>([
  { provider: 'anthropic', model: MODELS_BY_PROVIDER.anthropic[0] },
  { provider: 'openai', model: MODELS_BY_PROVIDER.openai[0] },
])

function updateLineup(index: number, spec: ModelSpec) {
  setLineup(lineup.map((existing, i) => (i === index ? spec : existing)))
}

function addModel() {
  if (lineup.length >= 4) return
  setLineup([...lineup, { provider: 'gemini', model: MODELS_BY_PROVIDER.gemini[0] }])
}

function removeModel(index: number) {
  if (lineup.length <= 2) return
  setLineup(lineup.filter((_, i) => i !== index))
}

const activeProviders = useMemo(
  () => Array.from(new Set(lineup.map((spec) => spec.provider))),
  [lineup],
)
```

Request construction becomes:

```tsx
const request: CompareRequest = {
  models: lineup,
  consistency_runs: consistencyRuns,
  run_id: newRunId,
  ...(mode === 'prompt' ? { prompt } : { suite_id: suiteId }),
}
```

- [ ] **Step 2: Render the lineup grid**

Replace the two hardcoded `<ModelPicker>`s with (reuse the existing `ModelPicker` component, adding an `onRemove` prop):

```tsx
<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
  {lineup.map((spec, index) => (
    <ModelPicker
      key={index}
      label={`Model ${index + 1}`}
      provider={spec.provider}
      model={spec.model}
      onProviderChange={(p) => updateLineup(index, { provider: p, model: MODELS_BY_PROVIDER[p][0] })}
      onModelChange={(m) => updateLineup(index, { ...spec, model: m })}
      onRemove={lineup.length > 2 ? () => removeModel(index) : undefined}
    />
  ))}
  {lineup.length < 4 && (
    <button
      type="button"
      onClick={addModel}
      className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted hover:text-text"
    >
      + Add model ({lineup.length}/4)
    </button>
  )}
</div>
```

In `ModelPicker`, add the optional remove button in the label row:

```tsx
<div className="flex items-center justify-between">
  <div className="font-mono-ui text-xs text-muted uppercase">{label}</div>
  {onRemove && (
    <button type="button" onClick={onRemove} className="font-mono-ui text-xs text-accent-red">
      remove
    </button>
  )}
</div>
```

Key inputs: change `(['anthropic', 'openai', 'gemini'] as const).map` to `activeProviders.map` so only providers actually in the lineup show a key field. `ProgressBar` call becomes `<ProgressBar state={stage} totalModels={lineup.length} />` (rename the `stage` variable to `progress` for clarity). Page heading: "Compare two models" → "Compare models".

- [ ] **Step 3: Verify compile**

Run: `cd frontend-src && npx tsc --noEmit`
Expected: no errors in `ComparePage.tsx` (Results/History/chart components still pending).

- [ ] **Step 4: Commit**

```bash
git add frontend-src/src/pages/ComparePage.tsx
git commit -m "feat(frontend): dynamic 2-4 model lineup on Compare page"
```

---

### Task 10: Results — leaderboard + N-model components

**Files:**
- Create: `frontend-src/src/components/Leaderboard.tsx`, `frontend-src/src/components/VerdictBanner.tsx`
- Delete: `frontend-src/src/components/WinnerBanner.tsx`
- Modify: `frontend-src/src/components/ModelCard.tsx`, `RadarMetrics.tsx`, `CostLatencyCharts.tsx`, `frontend-src/src/pages/ResultsPage.tsx`

**Interfaces:**
- Consumes: list-shaped `CompareResponse` (Task 8), `MODEL_SERIES_COLORS`.
- Produces: `<VerdictBanner response={CompareResponse} />`, `<Leaderboard results={ModelResult[]} />`, `<RadarMetrics results={ModelResult[]} />`, `<CostLatencyCharts results={ModelResult[]} />`, `<ModelCard result={ModelResult} />` — all N-model.

- [ ] **Step 1: Create `VerdictBanner.tsx`**

```tsx
import type { CompareResponse } from '../types'

export default function VerdictBanner({ response }: { response: CompareResponse }) {
  const winner = response.results[0]
  const isTie = response.results.filter((r) => r.rank === 1).length > 1
  const scoreLine = response.results
    .map((r) => (r.aggregate_score === null ? '—' : r.aggregate_score.toFixed(2)))
    .join(' vs ')

  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-6 py-4">
      <div>
        <div className="font-mono-ui text-xs text-muted">{isTie ? 'Result' : 'Winner'}</div>
        <div className={`text-2xl font-bold ${isTie ? 'text-accent-orange' : 'text-accent-green'}`}>
          {isTie ? 'Tie' : `${winner.model} wins`}
        </div>
        <div className="font-mono-ui text-xs text-muted">{scoreLine}</div>
      </div>
      <div className="font-mono-ui text-xs text-muted">Run {response.run_id.slice(0, 8)}</div>
    </div>
  )
}
```

- [ ] **Step 2: Create `Leaderboard.tsx`**

```tsx
import type { ModelResult } from '../types'

function usd(value: number | null): string {
  return value === null ? '—' : `$${value.toFixed(4)}`
}

function num(value: number | null, digits = 2, suffix = ''): string {
  return value === null ? '—' : `${value.toFixed(digits)}${suffix}`
}

export default function Leaderboard({ results }: { results: ModelResult[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-surface font-mono-ui text-xs text-muted uppercase">
          <tr>
            <th className="px-3 py-3">#</th>
            <th className="px-3 py-3">Model</th>
            <th className="px-3 py-3">Aggregate</th>
            <th className="px-3 py-3">Cost</th>
            <th className="px-3 py-3">Cost/task</th>
            <th className="px-3 py-3">Cost/1k tasks</th>
            <th className="px-3 py-3">p50</th>
            <th className="px-3 py-3">Tok/s</th>
            <th className="px-3 py-3">Consistency</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <tr key={`${r.model}-${r.rank}`} className="border-t border-border">
              <td className="px-3 py-3 font-mono-ui">
                {r.rank === 1 && !r.error ? '🏆' : r.rank}
              </td>
              <td className="px-3 py-3">
                <span className="font-semibold">{r.model}</span>{' '}
                <span className="font-mono-ui text-xs text-accent-purple">{r.provider}</span>
                {r.error && (
                  <span className="ml-2 rounded-full bg-accent-red/15 px-2 py-0.5 font-mono-ui text-xs text-accent-red">
                    failed
                  </span>
                )}
              </td>
              <td className="px-3 py-3 text-accent-blue">{num(r.aggregate_score)}</td>
              <td className="px-3 py-3 text-accent-orange">{usd(r.cost_usd)}</td>
              <td className="px-3 py-3">{usd(r.cost_per_task)}</td>
              <td className="px-3 py-3">{usd(r.cost_per_1k_tasks)}</td>
              <td className="px-3 py-3">{num(r.latency_ms, 0, ' ms')}</td>
              <td className="px-3 py-3">{num(r.tokens_per_sec, 1)}</td>
              <td className="px-3 py-3">{num(r.consistency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: Generalize `RadarMetrics.tsx` and `CostLatencyCharts.tsx` to `results: ModelResult[]`**

`RadarMetrics`: props become `{ results }: { results: ModelResult[] }`; build `metricNames` from all results; data rows `{ metric, [r.model]: score }`; render one `<Radar>` per result using `MODEL_SERIES_COLORS[i % 4]` for stroke/fill, `name={r.model}` `dataKey={r.model}`. (Duplicate model names in one run collide as dataKeys — acceptable; they're the same model.)

`CostLatencyCharts`: props become `{ results }`; `costData = results.map((r) => ({ name: r.model, cost: r.cost_usd }))`, same for latency. Chart JSX unchanged.

- [ ] **Step 4: Update `ModelCard.tsx` stat tiles**

Signature stays `{ label, result }`. Add three tiles to the stats grid after "Cost" (same tile markup pattern as existing):

```tsx
{result.cost_per_1k_tasks !== null && (
  <div className="rounded-md bg-bg p-2">
    <div className="text-muted">Cost / 1k tasks</div>
    <div className="text-accent-orange">${result.cost_per_1k_tasks.toFixed(2)}</div>
  </div>
)}
{result.tokens_per_sec !== null && (
  <div className="rounded-md bg-bg p-2">
    <div className="text-muted">Tokens/sec</div>
    <div className="text-accent-blue">{result.tokens_per_sec.toFixed(1)}</div>
  </div>
)}
{result.aggregate_score !== null && (
  <div className="rounded-md bg-bg p-2">
    <div className="text-muted">Aggregate score</div>
    <div className="text-accent-green">{result.aggregate_score.toFixed(2)}</div>
  </div>
)}
```

- [ ] **Step 5: Rewrite `ResultsPage.tsx` body**

Keep all loading/demo/error logic identical. Replace the render section from `<WinnerBanner ...>` down:

```tsx
<VerdictBanner response={result} />
<div className="flex justify-end">
  <Link
    to={`/report/${result.run_id}`}
    className="rounded-md bg-accent-blue px-4 py-2 text-sm font-semibold text-bg"
  >
    View report →
  </Link>
</div>
<Leaderboard results={result.results} />
<div
  className={`grid grid-cols-1 gap-4 ${
    result.results.length <= 2 ? 'md:grid-cols-2' : 'md:grid-cols-2 xl:grid-cols-2'
  }`}
>
  {result.results.map((r, i) => (
    <ModelCard key={`${r.model}-${i}`} label={`#${r.rank}`} result={r} />
  ))}
</div>
<RadarMetrics results={result.results} />
<CostLatencyCharts results={result.results} />
```

Imports: swap `WinnerBanner` for `VerdictBanner` + `Leaderboard`, add `Link` from `react-router-dom`. Delete `WinnerBanner.tsx`.

- [ ] **Step 6: Verify compile**

Run: `cd frontend-src && npx tsc --noEmit`
Expected: errors remain ONLY in `HistoryPage.tsx` (Task 12) — nothing else.

- [ ] **Step 7: Commit**

```bash
git add frontend-src/src/components frontend-src/src/pages/ResultsPage.tsx
git rm frontend-src/src/components/WinnerBanner.tsx 2>/dev/null || true
git commit -m "feat(frontend): leaderboard, verdict banner, N-model results view"
```

---

### Task 11: Report page + print CSS + route

**Files:**
- Create: `frontend-src/src/pages/ReportPage.tsx`
- Modify: `frontend-src/src/App.tsx` (route), `frontend-src/src/index.css` (print rules)

**Interfaces:**
- Consumes: `getRun`, `reportMdUrl` (Task 8), `VerdictBanner`/`Leaderboard`/`RadarMetrics`/`CostLatencyCharts` (Task 10).
- Produces: route `/report/:runId`; print-safe report; `.no-print` utility class.

- [ ] **Step 1: Create `ReportPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getRun, reportMdUrl } from '../lib/api'
import CostLatencyCharts from '../components/CostLatencyCharts'
import Leaderboard from '../components/Leaderboard'
import RadarMetrics from '../components/RadarMetrics'
import VerdictBanner from '../components/VerdictBanner'
import type { CompareResponse } from '../types'

export default function ReportPage() {
  const { runId } = useParams<{ runId: string }>()
  const [result, setResult] = useState<CompareResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) return
    getRun(runId)
      .then(setResult)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load run.'))
  }, [runId])

  if (error) {
    return (
      <div className="rounded-md border border-accent-red/30 bg-accent-red/10 p-4 text-sm text-accent-red">
        {error}
      </div>
    )
  }
  if (!result) return <div className="font-mono-ui text-sm text-muted">Loading report…</div>

  return (
    <div className="print-report flex flex-col gap-6">
      <div className="no-print flex items-center justify-between">
        <h1 className="text-3xl font-bold">Comparison Report</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded-md bg-surface px-4 py-2 text-sm font-mono-ui"
          >
            Print / Save PDF
          </button>
          <a
            href={reportMdUrl(result.run_id)}
            className="rounded-md bg-accent-blue px-4 py-2 text-sm font-semibold text-bg"
          >
            Download .md
          </a>
        </div>
      </div>

      <div className="font-mono-ui text-xs text-muted">
        Run {result.run_id} · {new Date(result.created_at).toLocaleString()} ·{' '}
        {result.results.length} models
      </div>

      <VerdictBanner response={result} />
      <Leaderboard results={result.results} />
      <RadarMetrics results={result.results} />
      <CostLatencyCharts results={result.results} />

      <div className="flex flex-col gap-4">
        <h2 className="text-xl font-bold">Responses</h2>
        {result.results.map((r, i) => (
          <details key={`${r.model}-${i}`} className="rounded-lg border border-border bg-surface p-4" open>
            <summary className="cursor-pointer font-semibold">
              #{r.rank} {r.model}{' '}
              <span className="font-mono-ui text-xs text-accent-purple">{r.provider}</span>
            </summary>
            {r.error ? (
              <div className="mt-3 rounded-md border border-accent-red/30 bg-accent-red/10 p-3 font-mono-ui text-sm text-accent-red">
                {r.error}
              </div>
            ) : (
              <pre className="mt-3 max-h-96 overflow-y-auto whitespace-pre-wrap rounded-md bg-bg p-3 font-mono-ui text-sm">
                {r.response_text || '(empty response)'}
              </pre>
            )}
          </details>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add route in `App.tsx`**

```tsx
import ReportPage from './pages/ReportPage'
// inside <Routes>, after the /results routes:
<Route path="/report/:runId" element={<ReportPage />} />
```

- [ ] **Step 3: Append print CSS to `index.css`**

```css
/* --- Print (report page -> browser Save-as-PDF) ------------------------- */
@media print {
  .no-print,
  header {
    display: none !important;
  }
  body {
    background: #ffffff !important;
    color: #111111 !important;
  }
  .print-report {
    color: #111111;
  }
  .print-report table,
  .print-report details {
    break-inside: avoid;
  }
  .print-report pre {
    max-height: none !important;
    overflow: visible !important;
  }
}
```

- [ ] **Step 4: Verify compile + commit**

Run: `cd frontend-src && npx tsc --noEmit` — only `HistoryPage.tsx` errors remain.

```bash
git add frontend-src/src/pages/ReportPage.tsx frontend-src/src/App.tsx frontend-src/src/index.css
git commit -m "feat(frontend): report page with print CSS and markdown download"
```

---

### Task 12: HistoryPage + demo data

**Files:**
- Modify: `frontend-src/src/pages/HistoryPage.tsx`, `frontend-src/public/demo/demo_results.json`

**Interfaces:**
- Consumes: `RunSummary.models` (Task 8), `/report/:runId` route (Task 11).

- [ ] **Step 1: Update HistoryPage table**

Replace the `Model A`/`Model B` columns with a single `Models` column plus a `Report` column; row click still navigates to `/results/${run.run_id}`:

```tsx
<thead className="bg-surface font-mono-ui text-xs text-muted uppercase">
  <tr>
    <th className="px-4 py-3">Date</th>
    <th className="px-4 py-3">Models</th>
    <th className="px-4 py-3">Winner</th>
    <th className="px-4 py-3">Report</th>
  </tr>
</thead>
<tbody>
  {runs.map((run) => (
    <tr
      key={run.run_id}
      className="cursor-pointer border-t border-border hover:bg-surface"
      onClick={() => navigate(`/results/${run.run_id}`)}
    >
      <td className="px-4 py-3 font-mono-ui text-xs text-muted">
        {new Date(run.created_at).toLocaleString()}
      </td>
      <td className="px-4 py-3">{run.models.join(' vs ')}</td>
      <td className="px-4 py-3">
        <span className={run.winner === 'tie' ? 'text-accent-orange' : 'text-accent-green'}>
          {run.winner === 'tie' ? 'Tie' : (run.winner ?? 'unknown')}
        </span>
      </td>
      <td className="px-4 py-3">
        <button
          type="button"
          className="font-mono-ui text-xs text-accent-blue"
          onClick={(e) => {
            e.stopPropagation()
            navigate(`/report/${run.run_id}`)
          }}
        >
          Open report →
        </button>
      </td>
    </tr>
  ))}
  ...empty-state row: colSpan={4} unchanged...
</tbody>
```

- [ ] **Step 2: Rewrite `frontend-src/public/demo/demo_results.json` as a 3-model run**

```json
{
  "run_id": "demo0000-0000-0000-0000-000000000000",
  "created_at": "2026-08-05T12:00:00+00:00",
  "ranking": ["claude-3-5-sonnet-20241022", "gpt-4o", "gemini-1.5-pro"],
  "results": [
    {
      "model": "claude-3-5-sonnet-20241022", "provider": "anthropic",
      "response_text": "Recursion is when a function calls itself to solve smaller instances of the same problem.\n\ndef factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\n\nThe base case (n <= 1) stops the recursion; each call reduces n, guaranteeing termination.",
      "input_tokens": 42, "output_tokens": 118, "latency_ms": 1240.0, "cost_usd": 0.00189,
      "judge_scores": {
        "correctness": {"score": 0.95, "reasoning": "Accurate definition with a correct, runnable example and base-case explanation."},
        "completeness": {"score": 0.92, "reasoning": "Covers definition, example, base case, and termination."},
        "safety": {"score": 1.0, "reasoning": "No safety concerns."}
      },
      "code_pass_rate": null, "consistency": null, "error": null,
      "aggregate_score": 0.9567, "rank": 1,
      "cost_per_task": 0.00189, "cost_per_1k_tasks": 1.89, "tokens_per_sec": 95.2
    },
    {
      "model": "gpt-4o", "provider": "openai",
      "response_text": "A recursive function solves a problem by calling itself with smaller input.\n\ndef fib(n):\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)\n\nNote: naive fib is exponential; memoize for real use.",
      "input_tokens": 42, "output_tokens": 96, "latency_ms": 980.0, "cost_usd": 0.00214,
      "judge_scores": {
        "correctness": {"score": 0.93, "reasoning": "Correct example with an appropriate performance caveat."},
        "completeness": {"score": 0.85, "reasoning": "Good but lighter on the termination explanation."},
        "safety": {"score": 1.0, "reasoning": "No safety concerns."}
      },
      "code_pass_rate": null, "consistency": null, "error": null,
      "aggregate_score": 0.9267, "rank": 2,
      "cost_per_task": 0.00214, "cost_per_1k_tasks": 2.14, "tokens_per_sec": 98.0
    },
    {
      "model": "gemini-1.5-pro", "provider": "gemini",
      "response_text": "Recursion means a function invokes itself.\n\ndef countdown(n):\n    if n == 0:\n        return\n    print(n)\n    countdown(n - 1)",
      "input_tokens": 42, "output_tokens": 61, "latency_ms": 1510.0, "cost_usd": 0.00098,
      "judge_scores": {
        "correctness": {"score": 0.88, "reasoning": "Correct but minimal example."},
        "completeness": {"score": 0.70, "reasoning": "Missing discussion of base cases and applications."},
        "safety": {"score": 1.0, "reasoning": "No safety concerns."}
      },
      "code_pass_rate": null, "consistency": null, "error": null,
      "aggregate_score": 0.86, "rank": 3,
      "cost_per_task": 0.00098, "cost_per_1k_tasks": 0.98, "tokens_per_sec": 40.4
    }
  ]
}
```

- [ ] **Step 3: Full frontend compile + build**

Run: `cd frontend-src && npx tsc --noEmit && npm run build`
Expected: zero TS errors; Vite build succeeds, output written to `../frontend`.

- [ ] **Step 4: Commit and push**

```bash
git add frontend-src/src/pages/HistoryPage.tsx frontend-src/public/demo/demo_results.json frontend
git commit -m "feat(frontend): N-model history, 3-model demo data, rebuilt frontend"
git push origin main
```

---

### Task 13: Full verification sweep

**Files:** none new — verification only.

- [ ] **Step 1: Backend gates**

Run: `python -m pytest tests/ -v` → ALL PASS.
Run: `ruff check .` → "All checks passed!".
Run: `mypy .` → "Success: no issues".

- [ ] **Step 2: Live smoke test (manual, no paid keys needed)**

Run: `uvicorn api.dashboard_server:app` then verify:
- `http://127.0.0.1:8000/dashboard` loads; Compare page shows 2 pickers + "+ Add model (2/4)".
- Results page in demo mode renders the 3-model leaderboard.
- Demo report: `http://127.0.0.1:8000/dashboard#/report/<any-existing-run-id>` renders (use an id from `/runs`; if the local DB has legacy runs, use one — this verifies the migration path end-to-end on real data).
- `http://127.0.0.1:8000/runs/<same-id>/report.md` downloads markdown.
- **Migration proof on real data:** confirm `database/arena.db.backup-*` was created on first startup and `GET /runs` still lists pre-existing runs.

- [ ] **Step 3: Fix anything found, commit**

```bash
git add -A
git commit -m "test: full verification sweep for N-model arena"
```

(Skip the commit if the sweep found nothing to change.)

---

### Task 14: Deploy verification + docs

**Files:**
- Modify: `README.md`, `docs/PROGRESS.md`
- Verify: `Dockerfile`, `render.yaml`, `vercel.json` (change only if the build proves it necessary)

- [ ] **Step 1: Docker build + container smoke test**

```bash
docker build -t llm-arena .
docker run -d -p 8000:8000 -e GROQ_API_KEY=dummy --name arena-smoke llm-arena
curl -s http://localhost:8000/ | grep -q "running"
curl -s http://localhost:8000/dashboard | grep -qi "html"
curl -s http://localhost:8000/suites | grep -q "reasoning"
docker rm -f arena-smoke
```

Expected: image builds (Node stage compiles the new frontend), all three curls succeed. If Docker is unavailable on this machine, run the equivalent uvicorn smoke from Task 13 Step 2 and note the limitation in the commit message.

- [ ] **Step 2: Update `README.md`**

- Overview: "Pick two models" → "Pick 2–4 models"; add report bullets (report page, print-to-PDF, `.md` export) to Features.
- Metrics list: add cost/task + cost-per-1k projection and tokens/sec.
- API Reference: add `GET /runs/{run_id}/report.md`; note `POST /compare` takes `models: [{provider, model}, ...]` (2–4).
- Build Phases: add "**Phase 6 — N-model arena + reports** ✅".
- Deployment: add the Render ephemeral-disk caveat: *"Render's free tier disk is ephemeral — SQLite history resets on redeploy. Attach a Render persistent disk to keep history across deploys. On startup the app backs up and migrates any existing `arena.db` automatically."*

- [ ] **Step 3: Update `docs/PROGRESS.md`** — mark the N-model arena phase complete with a one-paragraph summary (schema v2 migration, N-model compare, reports, deploy verified).

- [ ] **Step 4: Final gates + commit + push**

Run: `python -m pytest tests/ -q && ruff check . && mypy .` → clean.

```bash
git add README.md docs/PROGRESS.md Dockerfile render.yaml vercel.json
git commit -m "docs: N-model arena phase complete; deploy verified"
git push origin main
```

---

## Self-Review Notes

- **Spec coverage:** migration §1 → Task 1; contracts §2 → Task 2; derived fields §2 → Tasks 3–4; flow §3 → Task 5; read path/legacy §1.4 → Task 6; markdown report §4B → Task 7; report page §4A → Task 11; frontend §5 → Tasks 8–12; errors §6 → Tasks 4/5/7 tests; testing §7 → per-task + Task 13; deploy §8 → Task 14. No gaps found.
- **Type consistency check:** `_rank_results` returns `tuple[list[ModelResult], list[str]]` everywhere it's referenced (Tasks 4, 5, 6). `ProgressState` shape matches between hook (Task 8) and ProgressBar/ComparePage (Tasks 8–9). `reportMdUrl` defined Task 8, consumed Task 11. `save_run` keys match between Task 1 and Task 5.
- **Known judgment calls:** ranking recomputed at read time (single source of truth = `_rank_results`); stored `ranking` JSON only feeds `GET /runs` summaries. `tokens_per_sec` documented as an estimate (percentile latency vs summed tokens).
