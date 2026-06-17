from simplr.parser import (
    find_first_error,
    find_independent_errors,
    find_warnings,
)


def test_first_error_compiler():
    log = """main.cpp:14:19: error: 'string' is not a member of 'std'
   14 | class Buffer<std::string> {
      |                   ^~~~~~
main.cpp:53:25: error: taking address of rvalue [-fpermissive]
   53 |     bool* ptr = &flags[0];
"""
    err = find_first_error(log)
    assert err is not None
    assert err.error_type == "compiler"
    assert err.file == "main.cpp"
    assert err.line_num == 14
    assert "string" in err.message


def test_first_error_system_header_skipped():
    log = """/usr/include/c++/16.1.1/bits/new_allocator.h:70:26: error: forming pointer to reference type
main.cpp:14:19: error: 'string' is not a member of 'std'
"""
    err = find_first_error(log)
    assert err is not None
    assert err.file == "main.cpp"


def test_first_error_cmake():
    log = """CMake Error at CMakeLists.txt:15 (add_executable):
  Cannot find source file:
    foo.cpp
"""
    err = find_first_error(log)
    assert err is not None
    assert err.error_type == "cmake"
    assert err.file == "CMakeLists.txt"
    assert err.line_num == 15


def test_first_error_fatal():
    log = """fatal error: stddef.h: No such file or directory
"""
    err = find_first_error(log)
    assert err is not None
    assert err.error_type == "fatal"


def test_first_error_linker():
    log = """main.cpp:(.text+0x12): undefined reference to `foo'
collect2: error: ld returned 1 exit status
"""
    err = find_first_error(log)
    assert err is not None
    assert err.error_type in ("linker_detail", "linker")


def test_no_error():
    log = """Compilation succeeded.
"""
    err = find_first_error(log)
    assert err is None


def test_independent_errors():
    log = """main.cpp:14:19: error: 'string' not a member
main.cpp:53:25: error: taking address of rvalue
other.cpp:10:5: error: use of undeclared identifier 'x'
/usr/include/bits/foo.h:20: error: sysheader stuff
"""
    first = find_first_error(log)
    assert first is not None
    assert first.file == "main.cpp"

    others = find_independent_errors(log, first)
    assert len(others) == 2
    assert others[0].file == "main.cpp"
    assert others[1].file == "other.cpp"


def test_warnings():
    log = """main.cpp:61:12: warning: reference to local variable returned
main.cpp:93:10: warning: unused variable 'x'
"""
    warnings = find_warnings(log)
    assert len(warnings) == 2
    assert "reference to local" in warnings[0].message
    assert warnings[0].file == "main.cpp"
    assert warnings[0].line_num == 61


def test_no_warnings_in_error_free_log():
    log = """All good.
"""
    warnings = find_warnings(log)
    assert len(warnings) == 0


def test_context_cropping():
    log = """line1
line2
line3
line4
line5
main.cpp:10:5: error: first error
   10 | int x = y;
  some more context
main.cpp:20:5: error: second error
"""
    first = find_first_error(log)
    assert first is not None
    assert first.line_num == 10
    assert "second error" not in first.context
