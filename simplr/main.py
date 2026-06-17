from __future__ import annotations

import argparse
import os
import shlex
import stat
import subprocess
import sys
import time

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config as cfg
from .cache import get_cached, set_cached
from .parser import find_first_error, find_independent_errors, find_warnings
from .providers import create_provider
from . import stats as st

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="simplr — Analyze build logs and explain errors",
    )
    subparsers = parser.add_subparsers(dest="command")

    parser.add_argument(
        "--model",
        help="Model name override for the configured provider",
    )
    parser.add_argument(
        "--warnings",
        action="store_true",
        help="Also parse and explain compiler warnings",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass LLM response cache",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch source files and auto-rebuild (requires [build] command in config)",
    )

    bp = subparsers.add_parser("build", help="Run cmake --build and pipe through simplr")
    bp.add_argument(
        "-C", dest="build_dir", default=None,
        help="Build directory (default: from config or 'build')",
    )
    bp.add_argument(
        "extra", nargs=argparse.REMAINDER,
        help="Extra cmake args (use -- before them)",
    )
    bp.add_argument("--model")
    bp.add_argument("--warnings", action="store_true")
    bp.add_argument("--no-cache", action="store_true")
    bp.add_argument("--watch", action="store_true")

    ep = subparsers.add_parser(
        "exec", help="Run arbitrary build command and pipe through simplr",
    )
    ep.add_argument(
        "command", nargs=argparse.REMAINDER,
        help="Command to run (use -- before the command)",
    )
    ep.add_argument("--model")
    ep.add_argument("--warnings", action="store_true")
    ep.add_argument("--no-cache", action="store_true")

    subparsers.add_parser("stats", help="Show error statistics")

    return parser.parse_args()


def stdin_is_piped() -> bool:
    try:
        mode = os.fstat(sys.stdin.fileno()).st_mode
        return stat.S_ISFIFO(mode) or stat.S_ISREG(mode)
    except OSError:
        return False


def resolve_config(args: argparse.Namespace) -> dict:
    config = cfg.load()
    provider_name = config["provider"]["name"]
    model = getattr(args, "model", None)
    if model:
        config[provider_name]["model"] = model
    return config


def run_analysis(
    log: str,
    config: dict,
    show_warnings: bool = False,
    no_cache: bool = False,
) -> None:
    error = find_first_error(log)

    if error is None:
        console.print()
        console.print("  ✔  No errors detected.", style="bold green")
        if show_warnings:
            _show_warnings(log, config)
        return

    st.log_error(error)

    console.print("\n  Analyzing...", style="bold")

    other_errors = find_independent_errors(log, error)

    provider = None
    explanation: str | None = None

    if not no_cache:
        ttl = config.get("cache", {}).get("ttl_days", 30)
        explanation = get_cached(error, ttl)

    if explanation is None:
        provider = create_provider(config)
        try:
            explanation = provider.explain_error(
                error, config["inference"], other_errors
            )
        except Exception as e:
            console.print(f"[red]Error during analysis:[/red] {e}")
            sys.exit(1)

        if not no_cache:
            set_cached(error, explanation)

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

    if other_errors:
        console.print()
        console.print("[bold]Other unrelated errors:[/bold]")
        for e in other_errors:
            loc = e.file or ""
            if loc and e.line_num:
                loc += f":{e.line_num}"
            label = f"[{e.error_type}]"
            if loc:
                console.print(f"  {label} {loc}: {e.message}", style="dim")
            else:
                console.print(f"  {label} {e.message}", style="dim")

    if show_warnings:
        _show_warnings(log, config, provider)


def _show_warnings(log: str, config: dict, provider=None) -> None:
    if provider is None:
        provider = create_provider(config)

    warnings = find_warnings(log)
    if not warnings:
        return

    w = warnings[0]
    console.print()
    console.print("  Explaining first warning...", style="bold")

    try:
        explanation = provider.explain_warning(w, config["inference"])
    except Exception as e:
        console.print(f"[red]Error during warning analysis:[/red] {e}")
        return

    header = Text()
    header.append("Warning", style="bold yellow")
    header.append(f" ({w.error_type})", style="bold")
    if w.file:
        header.append(f" in {w.file}", style="bold")
    if w.line_num:
        header.append(f":{w.line_num}", style="bold")

    panel = Panel(
        Markdown(explanation),
        title=header,
        title_align="left",
        border_style="yellow",
        padding=(1, 2),
    )
    console.print(panel)

    if len(warnings) > 1:
        console.print()
        console.print("[bold]Other warnings:[/bold]")
        for w2 in warnings[1:]:
            loc = w2.file or ""
            if loc and w2.line_num:
                loc += f":{w2.line_num}"
            console.print(f"  {loc}: {w2.message}", style="dim")


def cmd_build(args: argparse.Namespace, config: dict) -> None:
    build_cfg = config.get("build", {})
    base_command = build_cfg.get("command", "").strip()

    if not base_command and not args.build_dir:
        console.print(
            "[red]No build command configured.[/red]\n"
            "  Set it in ~/.config/simplr/config.toml:\n"
            '    [build]\n'
            '    command = "cmake --build build"\n'
            "  Or use: simplr build -C <build-dir>",
        )
        sys.exit(1)

    extra = [a for a in (args.extra or []) if a != "--"]

    if args.build_dir:
        cmd = f"cmake --build {shlex.quote(args.build_dir)}"
    else:
        cmd = base_command

    if extra:
        cmd += " " + " ".join(shlex.quote(a) for a in extra)

    console.print(f"  Running: {cmd}", style="dim")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log = result.stdout + result.stderr

    sys.stdout.write(log)
    sys.stdout.write("\n")
    sys.stdout.flush()

    if args.watch:
        _watch_and_rebuild(args, config, cmd)
    else:
        run_analysis(
            log, config,
            show_warnings=args.warnings,
            no_cache=args.no_cache,
        )

    if result.returncode != 0:
        sys.exit(result.returncode)


def cmd_exec(args: argparse.Namespace, config: dict) -> None:
    cmd_parts = [a for a in (args.command or []) if a != "--"]
    if not cmd_parts:
        console.print("[red]No command specified.[/red]\n"
                       "  Usage: simplr exec -- <command...>")
        sys.exit(1)

    cmd = " ".join(shlex.quote(a) for a in cmd_parts)
    console.print(f"  Running: {cmd}", style="dim")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log = result.stdout + result.stderr

    sys.stdout.write(log)
    sys.stdout.write("\n")
    sys.stdout.flush()

    run_analysis(
        log, config,
        show_warnings=args.warnings,
        no_cache=args.no_cache,
    )

    if result.returncode != 0:
        sys.exit(result.returncode)


def cmd_stats() -> None:
    total = st.get_total_count()
    today = st.get_today_count()

    console.print()
    console.print(f"[bold]Error stats[/bold]  —  {total} total, {today} today")
    console.print()

    top = st.get_top_errors(10)
    if top:
        table = Table(title="Most frequent errors")
        table.add_column("Count", style="bold")
        table.add_column("Error")
        table.add_column("Location")
        for entry in top:
            loc = entry["file"] or ""
            if entry["line"]:
                loc += f":{entry['line']}"
            table.add_row(
                str(entry["count"]),
                entry["message"][:60],
                loc,
            )
        console.print(table)
        console.print()

    by_file = st.get_errors_by_file()
    if by_file:
        ftable = Table(title="Errors by file")
        ftable.add_column("Count", style="bold")
        ftable.add_column("File")
        for entry in by_file:
            loc = entry["file"] or "(unknown)"
            ftable.add_row(str(entry["count"]), loc)
        console.print(ftable)


def _watch_and_rebuild(
    args: argparse.Namespace,
    config: dict,
    build_cmd: str,
) -> None:
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        console.print(
            "[red]watchdog not installed.[/red]\n"
            "  Install it: uv sync --extra watch",
        )
        sys.exit(1)

    class RebuildHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.is_directory:
                return
            if not event.src_path.endswith((".cpp", ".h", ".hpp", ".c", ".cc", ".cxx")):
                return
            console.print(f"\n  Change detected: {event.src_path}", style="dim")
            console.print("  Rebuilding...", style="bold")
            result = subprocess.run(
                build_cmd, shell=True, capture_output=True, text=True,
            )
            log = result.stdout + result.stderr
            sys.stdout.write(log)
            sys.stdout.write("\n")
            sys.stdout.flush()
            run_analysis(
                log, config,
                show_warnings=args.warnings,
                no_cache=args.no_cache,
            )

    project_root = os.getcwd()
    event_handler = RebuildHandler()
    observer = Observer()
    observer.schedule(event_handler, project_root, recursive=True)
    observer.start()
    console.print(f"  Watching {project_root} for changes... (Ctrl+C to stop)", style="bold green")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def main() -> None:
    args = parse_args()
    config = resolve_config(args)

    cfg.ensure_default_config()

    if args.command == "stats":
        cmd_stats()
        return

    if args.command == "build":
        cmd_build(args, config)
        return

    if args.command == "exec":
        cmd_exec(args, config)
        return

    # Default pipe mode
    if not stdin_is_piped():
        console.print(
            "No input detected. Pipe a build log:\n"
            "  cmake --build build 2>&1 | simplr\n"
            "  simplr < build.log\n"
            "  simplr build\n"
            "  simplr exec -- <command>",
            style="dim",
        )
        sys.exit(1)

    log = sys.stdin.read()

    sys.stdout.write(log)
    sys.stdout.write("\n")
    sys.stdout.flush()

    if args.watch:
        build_cfg = config.get("build", {})
        base_command = build_cfg.get("command", "").strip()
        if not base_command:
            console.print(
                "[red]--watch requires [build] command in config.[/red]\n"
                "  Set it in ~/.config/simplr/config.toml:\n"
                '    [build]\n'
                '    command = "cmake --build build"',
            )
            sys.exit(1)
        _watch_and_rebuild(args, config, base_command)
        return

    run_analysis(
        log, config,
        show_warnings=args.warnings,
        no_cache=args.no_cache,
    )
