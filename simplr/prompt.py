from __future__ import annotations

from .parser import ErrorInfo

SYSTEM_PROMPT = (
    "You are a C/C++ build error explainer. Your job is to:\n"
    "1. Explain the error in simple terms (like explaining to a 12-year-old)\n"
    "2. Suggest a specific, actionable fix\n\n"
    "Focus ONLY on the first error. Ignore any cascading errors after it.\n"
    "If you are unsure about something, say so rather than guessing."
)


def build_user_prompt(error: ErrorInfo) -> str:
    header = f"Error Type: {error.error_type}"
    if error.file:
        header += f"\nFile: {error.file}"
    if error.line_num:
        header += f"\nLine: {error.line_num}"

    return (
        f"Here is a C/C++ build log snippet containing an error:\n\n"
        f"```\n{error.context}\n```\n\n"
        f"{header}\n\n"
        f"Explain what went wrong and how to fix it."
    )


def build_messages(error: ErrorInfo) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(error)},
    ]
