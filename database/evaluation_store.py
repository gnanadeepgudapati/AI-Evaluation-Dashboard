# evaluation_store.py
# Handles all database operations — saving and retrieving evaluations.
# Uses SQLite because it's built into Python and needs zero setup.

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "evaluations.db")


def get_connection():
    # Creates a connection to the database file
    # If the file doesn't exist, SQLite creates it automatically
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name instead of index
    return conn


def initialize_database():
    # Creates the evaluations table if it doesn't already exist
    # Safe to call every time the server starts
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            groundedness_score REAL,
            groundedness_reasoning TEXT,
            relevance_score REAL,
            relevance_reasoning TEXT,
            safety_score REAL,
            safety_reasoning TEXT,
            completeness_score REAL,
            completeness_reasoning TEXT,
            overall_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_evaluation(result: dict):
    # Saves one evaluation result to the database
    conn = get_connection()
    conn.execute("""
        INSERT INTO evaluations (
            id, question,
            groundedness_score, groundedness_reasoning,
            relevance_score, relevance_reasoning,
            safety_score, safety_reasoning,
            completeness_score, completeness_reasoning,
            overall_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        result["evaluation_id"],
        result["question"],
        result["groundedness"]["score"],
        result["groundedness"]["reasoning"],
        result["relevance"]["score"],
        result["relevance"]["reasoning"],
        result["safety"]["score"],
        result["safety"]["reasoning"],
        result["completeness"]["score"],
        result["completeness"]["reasoning"],
        result["overall_score"]
    ))
    conn.commit()
    conn.close()


def get_all_evaluations():
    # Returns every evaluation from the database, newest first
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM evaluations ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_evaluation_by_id(evaluation_id: str):
    # Returns one specific evaluation by its ID
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM evaluations WHERE id = ?
    """, (evaluation_id,)).fetchone()
    conn.close()
    return dict(row) if row else None