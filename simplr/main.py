from __future__ import annotations

import argparse
import os
import stat
import sys

from . import config as cfg
from .parser import find_first_error
from .providers import create_provider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="simplr — Analyze CMake build logs and explain errors",
        epilog="Usage: cmake --build build 2>&1 | simplr",
    )
    parser.add_argument(
        "--model",
        help="Model name override for the configured provider",
    )
    return parser.parse_args()


def stdin_is_piped() -> bool:
    mode = os.fstat(sys.stdin.fileno()).st_mode
    return stat.S_ISFIFO(mode) or stat.S_ISREG(mode)


def main() -> None:
    args = parse_args()

    if not stdin_is_piped():
        print(
            "No input detected. Pipe a CMake build log:\n"
            "  cmake --build build 2>&1 | simplr\n"
            "  simplr < build.log",
            file=sys.stderr,
        )
        sys.exit(1)

    log = sys.stdin.read()

    error = find_first_error(log)
    if error is None:
        print("No build errors detected.")
        return

    config = cfg.load()

    provider_name = config["provider"]["name"]
    if args.model:
        config[provider_name]["model"] = args.model

    cfg.ensure_default_config()

    provider = create_provider(config)

    try:
        explanation = provider.explain_error(error, config["inference"])
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        sys.exit(1)

    header = f"Error: {error.error_type}"
    if error.file:
        header += f" in {error.file}"
    if error.line_num:
        header += f":{error.line_num}"
    print(header)
    print()
    print(explanation)
