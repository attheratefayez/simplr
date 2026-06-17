from __future__ import annotations

import hashlib
import time

from .db import get_db
from .parser import ErrorInfo


def _make_key(error: ErrorInfo) -> str:
    raw = f"{error.file}:{error.line_num}:{error.message}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached(error: ErrorInfo, ttl_days: int = 30) -> str | None:
    conn = get_db()
    key = _make_key(error)
    row = conn.execute(
        "SELECT response, timestamp FROM cache WHERE hash = ?", (key,)
    ).fetchone()
    if row is None:
        conn.close()
        return None
    response, timestamp = row
    age_seconds = time.time() - timestamp
    if age_seconds > ttl_days * 86400:
        conn.execute("DELETE FROM cache WHERE hash = ?", (key,))
        conn.commit()
        conn.close()
        return None
    conn.close()
    return response


def set_cached(error: ErrorInfo, response: str) -> None:
    conn = get_db()
    key = _make_key(error)
    conn.execute(
        "INSERT OR REPLACE INTO cache (hash, response, timestamp) VALUES (?, ?, ?)",
        (key, response, time.time()),
    )
    conn.commit()
    conn.close()
