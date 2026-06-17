from __future__ import annotations

import re
from typing import NamedTuple

CONTEXT_BEFORE = 5
CONTEXT_AFTER = 15


class ErrorInfo(NamedTuple):
    error_type: str
    file: str | None
    line_num: int | None
    message: str
    context: str


PATTERNS: list[tuple[str, str]] = [
    # CMake Error at file:line (function):
    (r'^CMake Error at (.+?):(\d+)(?: \((.*?)\))?:\s*(.*)', "cmake"),
    # file:line:col: (fatal )?error:
    (r'^(.+?):(\d+):(\d+):\s+(?:fatal\s+)?error:\s*(.*)', "compiler"),
    # file:line: (fatal )?error:
    (r'^(.+?):(\d+):\s+(?:fatal\s+)?error:\s*(.*)', "compiler_nocol"),
    # linker: undefined reference
    (r'(undefined reference to|undefined symbol|unresolved external symbol)',
     "linker"),
    # fatal error: (no file/line)
    (r'^fatal error:\s*(.*)', "fatal"),
    # collect2 / ld fatal
    (r'^(collect2|ld):\s+fatal:\s*(.*)', "linker"),
]

def find_first_error(log: str) -> ErrorInfo | None:
    lines = log.splitlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        for pattern, error_type in PATTERNS:
            match = re.search(pattern, stripped, re.IGNORECASE)
            if match:
                start = max(0, i - CONTEXT_BEFORE)
                end = min(len(lines), i + CONTEXT_AFTER)
                context = "\n".join(lines[start:end])

                if error_type == "cmake":
                    file = match.group(1)
                    line_num = int(match.group(2))
                    msg = match.group(4).strip()
                elif error_type == "compiler":
                    file = match.group(1)
                    line_num = int(match.group(2))
                    msg = match.group(4).strip()
                elif error_type == "compiler_nocol":
                    file = match.group(1)
                    line_num = int(match.group(2))
                    msg = match.group(3).strip()
                elif error_type == "linker":
                    file = None
                    line_num = None
                    msg = stripped
                elif error_type == "fatal":
                    file = None
                    line_num = None
                    msg = match.group(1).strip()
                else:
                    file = None
                    line_num = None
                    msg = stripped

                return ErrorInfo(
                    error_type=error_type,
                    file=file,
                    line_num=line_num,
                    message=msg,
                    context=context,
                )

    return None
