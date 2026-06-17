from __future__ import annotations

import argparse
import os
import stat
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from . import config as cfg
from .parser import find_first_error
from .providers import create_provider

console = Console()


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
        console.print(
            "No input detected. Pipe a CMake build log:\n"
            "  cmake --build build 2>&1 | simplr\n"
            "  simplr < build.log",
            style="dim",
        )
        sys.exit(1)

    log = sys.stdin.read()

    error = find_first_error(log)
    if error is None:
        console.print("No build errors detected.", style="dim")
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
        console.print(f"[red]Error during analysis:[/red] {e}")
        sys.exit(1)

    header = Text()
    header.append("Error", style="bold yellow")
    header.append(f" ({error.error_type})", style="bold")
    if error.file:
        header.append(f" in {error.file}", style="bold")
    if error.line_num:
        header.append(f":{error.line_num}", style="bold")

    panel = Panel(
        Markdown(explanation),
        title=header,
        title_align="left",
        border_style="yellow",
        padding=(1, 2),
    )
    console.print(panel)
