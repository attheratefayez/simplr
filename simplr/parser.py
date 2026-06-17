from __future__ import annotations

import re
from typing import NamedTuple

CONTEXT_BEFORE = 5
MAX_CONTEXT_AFTER = 6


class ErrorInfo(NamedTuple):
    error_type: str
    file: str | None
    line_num: int | None
    message: str
    context: str


class IndependentError(NamedTuple):
    file: str | None
    line_num: int | None
    message: str
    error_type: str


PATTERNS: list[tuple[str, str]] = [
    (r'^CMake Error at (.+?):(\d+)(?: \((.*?)\))?:\s*(.*)', "cmake"),
    (r'^(.+?):(\d+):(\d+):\s+(?:fatal\s+)?error:\s*(.*)', "compiler"),
    (r'^(.+?):(\d+):\s+(?:fatal\s+)?error:\s*(.*)', "compiler_nocol"),
    (r'(undefined reference to|undefined symbol|unresolved external symbol)',
     "linker"),
    (r'^fatal error:\s*(.*)', "fatal"),
    (r'^(collect2|ld):\s+fatal:\s*(.*)', "linker"),
]


def _match_line(line: str) -> tuple[re.Match, str] | None:
    stripped = line.strip()
    for pattern, error_type in PATTERNS:
        match = re.search(pattern, stripped, re.IGNORECASE)
        if match:
            return match, error_type
    return None


def _extract_info(
    match: re.Match, error_type: str, line: str
) -> tuple[str | None, int | None, str]:
    stripped = line.strip()
    if error_type == "cmake":
        return match.group(1), int(match.group(2)), match.group(4).strip()
    if error_type == "compiler":
        return match.group(1), int(match.group(2)), match.group(4).strip()
    if error_type == "compiler_nocol":
        return match.group(1), int(match.group(2)), match.group(3).strip()
    if error_type == "fatal":
        return None, None, match.group(1).strip()
    return None, None, stripped


def find_first_error(log: str) -> ErrorInfo | None:
    lines = log.splitlines()

    for i, line in enumerate(lines):
        r = _match_line(line)
        if r is None:
            continue
        match, error_type = r

        start = max(0, i - CONTEXT_BEFORE)

        end = min(len(lines), i + MAX_CONTEXT_AFTER + 1)
        for j in range(i + 1, min(len(lines), i + MAX_CONTEXT_AFTER + 1)):
            if _match_line(lines[j]) is not None:
                end = j
                break

        context = "\n".join(lines[start:end])
        file, line_num, msg = _extract_info(match, error_type, line)

        return ErrorInfo(
            error_type=error_type,
            file=file,
            line_num=line_num,
            message=msg,
            context=context,
        )

    return None


def find_independent_errors(
    log: str, first: ErrorInfo
) -> list[IndependentError]:
    lines = log.splitlines()
    results: list[IndependentError] = []

    first_idx = -1
    for i, line in enumerate(lines):
        r = _match_line(line)
        if r is None:
            continue
        match, et = r
        f, ln, msg = _extract_info(match, et, line)
        if (
            f == first.file
            and ln == first.line_num
            and et == first.error_type
            and msg == first.message
        ):
            first_idx = i
            break

    if first_idx == -1:
        return results

    for i in range(first_idx + 1, len(lines)):
        r = _match_line(lines[i])
        if r is None:
            continue
        match, et = r
        f, ln, msg = _extract_info(match, et, lines[i])

        independent = False
        if et != first.error_type:
            independent = True
        elif f is not None and f != first.file:
            independent = True

        if independent:
            results.append(
                IndependentError(
                    file=f,
                    line_num=ln,
                    message=msg,
                    error_type=et,
                )
            )

    return results
