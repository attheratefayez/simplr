from __future__ import annotations

from .parser import ErrorInfo, IndependentError

SYSTEM_PROMPT = (
    "You are a C/C++ build error explainer. Your job is to:\n"
    "1. Explain ONLY the first error in simple terms\n"
    "2. Suggest a specific, actionable fix\n\n"
    "Ignore cascading errors caused by the first error. "
    "If the user mentions other unrelated errors, briefly note them "
    "but keep your focus on the first error.\n"
    "If you are unsure, say so rather than guessing."
)


def build_user_prompt(
    error: ErrorInfo,
    independent_errors: list[IndependentError] | None = None,
) -> str:
    header = f"Error Type: {error.error_type}"
    if error.file:
        header += f"\nFile: {error.file}"
    if error.line_num:
        header += f"\nLine: {error.line_num}"

    parts = [
        "Here is a C/C++ build log snippet containing the first error:",
        "",
        f"```\n{error.context}\n```",
        "",
        header,
        "",
        "Explain what went wrong and how to fix it.",
    ]

    if independent_errors:
        lines = []
        for e in independent_errors:
            loc = e.file or ""
            if loc and e.line_num:
                loc += f":{e.line_num}"
            if loc:
                lines.append(f"- [{e.error_type}] {loc}: {e.message}")
            else:
                lines.append(f"- [{e.error_type}] {e.message}")

        parts += [
            "",
            "There are other unrelated errors in different files or of "
            "different types:",
            *lines,
            "",
            "Briefly note these exist, but focus on the first error above.",
        ]

    return "\n".join(parts)


def build_messages(
    error: ErrorInfo,
    independent_errors: list[IndependentError] | None = None,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_user_prompt(error, independent_errors),
        },
    ]
