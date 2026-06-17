from __future__ import annotations

import hashlib
import time
from typing import Any

from .db import get_db
from .parser import ErrorInfo


def _make_hash(error: ErrorInfo) -> str:
    raw = f"{error.file}:{error.line_num}:{error.message}"
    return hashlib.sha256(raw.encode()).hexdigest()


def log_error(error: ErrorInfo) -> None:
    conn = get_db()
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
    conn = get_db()
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
    conn = get_db()
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
    conn = get_db()
    today_start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, 0))
    row = conn.execute(
        "SELECT COUNT(*) FROM errors WHERE timestamp >= ?",
        (today_start,),
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def get_total_count() -> int:
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) FROM errors").fetchone()
    conn.close()
    return row[0] if row else 0
