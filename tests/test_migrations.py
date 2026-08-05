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
        version_row = await cursor.fetchone()
        assert version_row is not None
        (version,) = version_row
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
        count_row = await cursor.fetchone()
        assert count_row is not None
        assert count_row[0] == 1
        cursor = await db.execute("SELECT COUNT(*) FROM metric_scores")
        count_row = await cursor.fetchone()
        assert count_row is not None
        assert count_row[0] == 1


async def test_migration_is_idempotent(tmp_path):
    db_path = str(tmp_path / "arena.db")
    _build_v1_db(db_path)

    await migrate_arena_db(db_path)
    await migrate_arena_db(db_path)  # second run must be a no-op

    backups = list(tmp_path.glob("arena.db.backup-*"))
    assert len(backups) == 1, "no second backup on a no-op re-run"

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM runs")
        count_row = await cursor.fetchone()
        assert count_row is not None
        assert count_row[0] == 2


async def test_migration_noop_on_missing_file(tmp_path):
    await migrate_arena_db(str(tmp_path / "does_not_exist.db"))  # must not raise
    assert not Path(tmp_path / "does_not_exist.db").exists()


async def test_migration_failure_rolls_back_everything(tmp_path):
    """A failure mid-migration must leave the DB exactly as it was:
    runs table intact, no orphan runs_new, version unchanged, error raised."""
    db_path = str(tmp_path / "arena.db")
    # Build a BROKEN v1 db: runs table missing the `winner` column, so the
    # INSERT ... SELECT inside the migration fails after CREATE TABLE runs_new.
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE runs (id TEXT PRIMARY KEY, suite_id TEXT, prompt TEXT, "
        "model_a TEXT NOT NULL, model_b TEXT NOT NULL, provider_a TEXT NOT NULL, "
        "provider_b TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
    )
    conn.execute(
        "INSERT INTO runs (id, model_a, model_b, provider_a, provider_b) "
        "VALUES ('r1', 'a', 'b', 'anthropic', 'openai')"
    )
    conn.commit()
    conn.close()

    with pytest.raises(sqlite3.OperationalError):
        await migrate_arena_db(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM runs")
        count_row = await cursor.fetchone()
        assert count_row is not None
        assert count_row[0] == 1  # original data untouched
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runs_new'"
        )
        assert await cursor.fetchone() is None  # no orphan table
        cursor = await db.execute("PRAGMA user_version")
        version_row = await cursor.fetchone()
        assert version_row is not None
        assert version_row[0] == 0


async def test_migration_recovers_from_orphaned_runs_new(tmp_path):
    """An orphan runs_new left by a hard crash must not block migration."""
    db_path = str(tmp_path / "arena.db")
    _build_v1_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE runs_new (junk TEXT)")
    conn.commit()
    conn.close()

    await migrate_arena_db(db_path)  # must succeed

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM runs")
        count_row = await cursor.fetchone()
        assert count_row is not None
        assert count_row[0] == 2
        cursor = await db.execute("PRAGMA user_version")
        version_row = await cursor.fetchone()
        assert version_row is not None
        assert version_row[0] == ARENA_SCHEMA_VERSION
