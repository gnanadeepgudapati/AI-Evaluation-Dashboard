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
