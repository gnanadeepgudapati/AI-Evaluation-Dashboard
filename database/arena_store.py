# arena_store.py
# Async persistence layer for the comparison arena. Separate from the legacy
# `evaluation_store.py` (which is left untouched for backward compatibility).

import os

import aiosqlite

DB_PATH = os.path.join(os.path.dirname(__file__), "arena.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
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

CREATE TABLE IF NOT EXISTS model_results (
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

CREATE TABLE IF NOT EXISTS metric_scores (
    id               TEXT PRIMARY KEY,
    model_result_id  TEXT NOT NULL REFERENCES model_results(id),
    metric_name      TEXT NOT NULL,
    score            REAL NOT NULL,
    reasoning        TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def initialize_arena_db() -> None:
    """Create the arena tables if they don't already exist. Safe to call repeatedly."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


async def save_run(run: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO runs (id, suite_id, prompt, model_a, model_b, provider_a, provider_b, winner)
            VALUES (:id, :suite_id, :prompt, :model_a, :model_b, :provider_a, :provider_b, :winner)
            """,
            run,
        )
        await db.commit()


async def save_model_result(result: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO model_results (
                id, run_id, slot, model_name, provider, response_text,
                input_tokens, output_tokens, latency_ms, cost_usd,
                code_pass_rate, consistency, error
            ) VALUES (
                :id, :run_id, :slot, :model_name, :provider, :response_text,
                :input_tokens, :output_tokens, :latency_ms, :cost_usd,
                :code_pass_rate, :consistency, :error
            )
            """,
            result,
        )
        await db.commit()


async def save_metric_score(score: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO metric_scores (id, model_result_id, metric_name, score, reasoning)
            VALUES (:id, :model_result_id, :metric_name, :score, :reasoning)
            """,
            score,
        )
        await db.commit()


async def get_run(run_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_runs(limit: int = 50, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_model_results_for_run(run_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM model_results WHERE run_id = ? ORDER BY slot", (run_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_metric_scores_for_result(model_result_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM metric_scores WHERE model_result_id = ?",
            (model_result_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
