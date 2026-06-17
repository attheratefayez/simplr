import time

from simplr.cache import get_cached, set_cached
from simplr.parser import ErrorInfo


def _make_error(file="main.cpp", line=10, msg="test error"):
    return ErrorInfo(
        error_type="compiler",
        file=file,
        line_num=line,
        message=msg,
        context="",
    )


def test_set_and_get():
    err = _make_error()
    set_cached(err, "explanation text")
    result = get_cached(err, ttl_days=30)
    assert result == "explanation text"


def test_cache_returns_none_for_unknown():
    err = _make_error(file="unknown.cpp")
    result = get_cached(err, ttl_days=30)
    assert result is None


def test_different_errors_different_cache():
    err1 = _make_error(msg="error one")
    err2 = _make_error(msg="error two")

    set_cached(err1, "response one")
    assert get_cached(err1) == "response one"
    assert get_cached(err2) is None


def test_cache_expiry():
    err = _make_error()
    set_cached(err, "stale response")

    # ttl_days=0 means anything older than 0 days is expired
    result = get_cached(err, ttl_days=0)
    assert result is None
