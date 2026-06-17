from __future__ import annotations

import sqlite3
from pathlib import Path

DB_DIR = Path.home() / ".config" / "simplr"
DB_PATH = DB_DIR / "simplr.sqlite3"


def get_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache ("
        "  hash TEXT PRIMARY KEY,"
        "  response TEXT NOT NULL,"
        "  timestamp REAL NOT NULL"
        ")"
    )
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_hash ON errors(hash)")
    conn.commit()
    return conn
