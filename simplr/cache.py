from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .parser import ErrorInfo

CACHE_DIR = Path.home() / ".config" / "simplr"
CACHE_PATH = CACHE_DIR / "cache.json"


def _make_key(error: ErrorInfo) -> str:
    raw = f"{error.file}:{error.line_num}:{error.message}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _load_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict[str, dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def get_cached(error: ErrorInfo, ttl_days: int = 30) -> str | None:
    cache = _load_cache()
    key = _make_key(error)
    entry = cache.get(key)
    if entry is None:
        return None
    age_seconds = time.time() - entry.get("timestamp", 0)
    if age_seconds > ttl_days * 86400:
        del cache[key]
        _save_cache(cache)
        return None
    return entry.get("response")


def set_cached(error: ErrorInfo, response: str) -> None:
    cache = _load_cache()
    key = _make_key(error)
    cache[key] = {
        "response": response,
        "timestamp": time.time(),
    }
    _save_cache(cache)
