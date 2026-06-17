from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Any

from .parser import ErrorInfo

STATS_DIR = Path.home() / ".config" / "simplr"
STATS_PATH = STATS_DIR / "stats.db"


def _get_db() -> sqlite3.Connection:
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(STATS_PATH))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  hash TEXT NOT NULL,"
        "  file TEXT,"
        "  line INTEGER,"
        "  type TEXT,"
        "  message TEXT,"
        "  timestamp REAL NOT NULL"
        ")"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_hash ON errors(hash)"
    )
    conn.commit()
    return conn


def _make_hash(error: ErrorInfo) -> str:
    raw = f"{error.file}:{error.line_num}:{error.message}"
    return hashlib.sha256(raw.encode()).hexdigest()


def log_error(error: ErrorInfo) -> None:
    conn = _get_db()
    conn.execute(
        "INSERT INTO errors (hash, file, line, type, message, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            _make_hash(error),
            error.file,
            error.line_num,
            error.error_type,
            error.message,
            time.time(),
        ),
    )
    conn.commit()
    conn.close()


def get_top_errors(limit: int = 10) -> list[dict[str, Any]]:
    conn = _get_db()
    rows = conn.execute(
        "SELECT file, line, message, type, COUNT(*) as cnt "
        "FROM errors "
        "GROUP BY hash "
        "ORDER BY cnt DESC "
        "LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {"file": r[0], "line": r[1], "message": r[2], "type": r[3], "count": r[4]}
        for r in rows
    ]


def get_errors_by_file() -> list[dict[str, Any]]:
    conn = _get_db()
    rows = conn.execute(
        "SELECT file, COUNT(*) as cnt "
        "FROM errors "
        "WHERE file IS NOT NULL "
        "GROUP BY file "
        "ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return [{"file": r[0], "count": r[1]} for r in rows]


def get_today_count() -> int:
    conn = _get_db()
    today_start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, 0))
    row = conn.execute(
        "SELECT COUNT(*) FROM errors WHERE timestamp >= ?",
        (today_start,),
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def get_total_count() -> int:
    conn = _get_db()
    row = conn.execute("SELECT COUNT(*) FROM errors").fetchone()
    conn.close()
    return row[0] if row else 0
