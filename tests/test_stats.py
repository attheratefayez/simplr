from simplr.parser import ErrorInfo
from simplr.stats import (
    log_error,
    get_top_errors,
    get_errors_by_file,
    get_total_count,
)


def _make_error(file="main.cpp", line=10, msg="test error"):
    return ErrorInfo(
        error_type="compiler",
        file=file,
        line_num=line,
        message=msg,
        context="",
    )


def test_log_and_count():
    before = get_total_count()
    log_error(_make_error())
    after = get_total_count()
    assert after == before + 1


def test_top_errors():
    log_error(_make_error(msg="frequent error"))
    log_error(_make_error(msg="frequent error"))
    top = get_top_errors(limit=5)
    frequent = [e for e in top if "frequent" in e["message"]]
    assert len(frequent) >= 1
    assert frequent[0]["count"] >= 2


def test_errors_by_file():
    log_error(_make_error(file="a.cpp"))
    log_error(_make_error(file="a.cpp"))
    log_error(_make_error(file="b.cpp"))
    by_file = get_errors_by_file()
    a_entries = [e for e in by_file if e["file"] == "a.cpp"]
    assert len(a_entries) == 1
    assert a_entries[0]["count"] >= 2
