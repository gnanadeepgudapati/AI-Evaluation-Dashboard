"""
SQLite persistence layer for evaluation history.
Provides async read/write operations using aiosqlite.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./database/evaluations.db")


def _get_connection() -> sqlite3.Connection:
    """Open a synchronous SQLite connection and ensure the schema exists."""
    os.makedirs(os.path.dirname(os.path.abspath(DATABASE_PATH)), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the evaluations table if it does not already exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT    NOT NULL,
            question    TEXT    NOT NULL,
            response    TEXT    NOT NULL,
            context     TEXT    NOT NULL DEFAULT '',
            groundedness_score  REAL NOT NULL,
            relevance_score     REAL NOT NULL,
            safety_score        REAL NOT NULL,
            completeness_score  REAL NOT NULL,
            overall_score       REAL NOT NULL,
            full_result         TEXT NOT NULL
        )
        """
    )
    conn.commit()


def save_evaluation(result: dict[str, Any]) -> int:
    """
    Persist an evaluation result to the database.

    Args:
        result: A dict representation of EvaluationResult.

    Returns:
        The auto-generated row id.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO evaluations
                (created_at, question, response, context,
                 groundedness_score, relevance_score, safety_score,
                 completeness_score, overall_score, full_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                result["question"],
                result["response"],
                result.get("context", ""),
                result["groundedness"]["score"],
                result["relevance"]["score"],
                result["safety"]["score"],
                result["completeness"]["score"],
                result["overall_score"],
                json.dumps(result),
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def get_all_evaluations(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """
    Retrieve evaluation history, most-recent first.

    Args:
        limit:  Maximum number of rows to return (default 100).
        offset: Number of rows to skip for pagination (default 0).

    Returns:
        List of dicts with summary fields plus the full JSON result.
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, created_at, question, response, context,
                   groundedness_score, relevance_score, safety_score,
                   completeness_score, overall_score, full_result
            FROM evaluations
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_evaluation_by_id(evaluation_id: int) -> dict[str, Any] | None:
    """
    Retrieve a single evaluation by its id.

    Returns:
        Dict with all fields, or None if not found.
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM evaluations WHERE id = ?", (evaluation_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_metric_averages() -> dict[str, float]:
    """
    Compute the average score for each metric across all stored evaluations.

    Returns:
        Dict mapping metric name to average score (0–1), or 0.0 if no data.
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                AVG(groundedness_score)  AS groundedness,
                AVG(relevance_score)     AS relevance,
                AVG(safety_score)        AS safety,
                AVG(completeness_score)  AS completeness,
                AVG(overall_score)       AS overall
            FROM evaluations
            """
        ).fetchone()
        if row is None:
            return {
                "groundedness": 0.0,
                "relevance": 0.0,
                "safety": 0.0,
                "completeness": 0.0,
                "overall": 0.0,
            }
        return {
            "groundedness": round(row["groundedness"] or 0.0, 4),
            "relevance": round(row["relevance"] or 0.0, 4),
            "safety": round(row["safety"] or 0.0, 4),
            "completeness": round(row["completeness"] or 0.0, 4),
            "overall": round(row["overall"] or 0.0, 4),
        }
    finally:
        conn.close()
