"""Database access helpers for the OBD-II MCP server."""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "obd2.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def lookup_code(code: str) -> dict | None:
    """Return the row for *code* or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT code, category, severity, description, symptoms, fix FROM dtc_codes WHERE code = ?",
            (code,),
        ).fetchone()
    return dict(row) if row else None


def search_symptoms(text: str, limit: int = 10) -> list[dict]:
    """Full-text search across description, symptoms, and fix via FTS5.

    Falls back to LIKE if the FTS table is not present (e.g. in older test DBs).
    """
    with get_connection() as conn:
        # Check whether FTS table exists
        fts_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dtc_codes_fts'"
        ).fetchone()
        if fts_exists:
            rows = conn.execute(
                """
                SELECT d.code, d.category, d.severity, d.description, d.symptoms, d.fix
                FROM dtc_codes_fts f
                JOIN dtc_codes d ON d.rowid = f.rowid
                WHERE dtc_codes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (text, limit),
            ).fetchall()
        else:
            # Fallback for test databases seeded without FTS
            pattern = f"%{text}%"
            rows = conn.execute(
                """
                SELECT code, category, severity, description, symptoms, fix
                FROM dtc_codes
                WHERE symptoms LIKE ?
                   OR description LIKE ?
                   OR fix LIKE ?
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            ).fetchall()
    return [dict(r) for r in rows]


def list_codes(
    category: str | None = None, limit: int = 100, offset: int = 0
) -> list[dict]:
    """Return codes, optionally filtered by category, with pagination support."""
    with get_connection() as conn:
        if category:
            rows = conn.execute(
                "SELECT code, category, severity, description FROM dtc_codes WHERE category = ? ORDER BY code LIMIT ? OFFSET ?",
                (category, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT code, category, severity, description FROM dtc_codes ORDER BY code LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return [dict(r) for r in rows]


def get_related_codes(code: str, limit: int = 10) -> list[dict]:
    """Return other codes in the same category as *code*, excluding *code* itself."""
    with get_connection() as conn:
        cat_row = conn.execute(
            "SELECT category FROM dtc_codes WHERE code = ?", (code,)
        ).fetchone()
        if cat_row is None:
            return []
        rows = conn.execute(
            """
            SELECT code, category, severity, description
            FROM dtc_codes
            WHERE category = ? AND code != ?
            ORDER BY code
            LIMIT ?
            """,
            (cat_row["category"], code, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def lookup_codes(codes: list[str]) -> list[dict]:
    """Return rows for all *codes* that exist, in code order."""
    if not codes:
        return []
    placeholders = ",".join("?" * len(codes))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT code, category, severity, description, symptoms, fix "
            f"FROM dtc_codes WHERE code IN ({placeholders}) ORDER BY code",
            codes,
        ).fetchall()
    return [dict(r) for r in rows]


def search_code_prefix(pattern: str, limit: int = 50) -> list[dict]:
    """Return codes whose code matches *pattern* using SQL LIKE.

    ``*`` is mapped to ``%`` and ``?`` to ``_``.  If the pattern contains no
    wildcard characters, a trailing ``%`` is appended so it acts as a prefix
    match (e.g. ``'P030'`` → ``'P030%'``).
    """
    sql_pattern = pattern.replace("*", "%").replace("?", "_")
    if "%" not in sql_pattern and "_" not in sql_pattern:
        sql_pattern = sql_pattern + "%"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT code, category, severity, description "
            "FROM dtc_codes WHERE code LIKE ? ORDER BY code LIMIT ?",
            (sql_pattern, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def count_codes(category: str | None = None, severity: str | None = None) -> int:
    """Return the total number of codes matching the given filters."""
    with get_connection() as conn:
        if category and severity:
            return conn.execute(
                "SELECT COUNT(*) FROM dtc_codes WHERE category = ? AND severity = ?",
                (category, severity),
            ).fetchone()[0]
        if category:
            return conn.execute(
                "SELECT COUNT(*) FROM dtc_codes WHERE category = ?",
                (category,),
            ).fetchone()[0]
        if severity:
            return conn.execute(
                "SELECT COUNT(*) FROM dtc_codes WHERE severity = ?",
                (severity,),
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM dtc_codes").fetchone()[0]


def get_all_codes() -> list[dict]:
    """Return every code (all columns) ordered by code, for export."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT code, category, severity, description, symptoms, fix "
            "FROM dtc_codes ORDER BY code"
        ).fetchall()
    return [dict(r) for r in rows]


def get_categories() -> list[str]:
    """Return sorted list of distinct category names."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM dtc_codes WHERE category != '' ORDER BY category"
        ).fetchall()
    return [r["category"] for r in rows]


def db_ping() -> bool:
    """Return True if the database is reachable and has data."""
    try:
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM dtc_codes").fetchone()[0]
        return count > 0
    except Exception:
        return False
