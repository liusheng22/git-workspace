from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .executor import process_env, resolve_command
from .models import ExecMode
from .output import plan_items_for_action, print_plan, print_status
from .planner import build_plan
from .tui import GitWorkspace
from .workspace import load_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gws",
        description="Git-aware multi-repo terminal workspace",
    )
    parser.add_argument("--cwd", type=Path, default=None, help="workspace start directory")

    sub = parser.add_subparsers(dest="command")

    status = sub.add_parser("status", aliases=["st", "s"], help="show workspace status")
    status.add_argument("profile", nargs="?")

    plan = sub.add_parser("plan", help="show workspace action plan")
    plan.add_argument("profile", nargs="?")

    switch = sub.add_parser("switch", help="checkout target branches from a profile")
    switch.add_argument("profile", nargs="?")

    pull = sub.add_parser("pull", help="pull repositories that are safe to update")
    pull.add_argument("profile", nargs="?")

    sync = sub.add_parser("sync", help="switch then pull repositories that are safe to update")
    sync.add_argument("profile", nargs="?")

    exec_cmd = sub.add_parser("exec", help="execute a command in every selected repository")
    exec_cmd.add_argument("tokens", nargs=argparse.REMAINDER, metavar="...")

    sub.add_parser("tui", help="open the TUI")
    return parser


def run_git(repo_path: Path, *args: str) -> int:
    proc = subprocess.run(
        ["git", "-C", str(repo_path), "--no-pager", *args],
        text=True,
        env=process_env(),
    )
    return proc.returncode


def do_switch(profile: str | None, start: Path | None) -> int:
    workspace = load_workspace(start)
    exit_code = 0
    for item in build_plan(workspace, profile):
        if item.action == "blocked":
            print(f"skip {item.repo.name}: {item.note}")
            exit_code = 1
            continue
        if item.current != item.target:
            print(f"== {item.repo.name}: checkout {item.target} ==")
            exit_code = run_git(item.repo.path, "checkout", item.target) or exit_code
    return exit_code


def do_pull(profile: str | None, start: Path | None) -> int:
    workspace = load_workspace(start)
    exit_code = 0
    for item in build_plan(workspace, profile):
        if item.action == "blocked":
            print(f"skip {item.repo.name}: {item.note}")
            exit_code = 1
            continue
        if item.action == "skip pull":
            print(f"skip {item.repo.name}: {item.note}")
            continue
        if item.action == "checkout + pull":
            hint = "run switch first or use sync"
            print(f"skip {item.repo.name}: target branch differs; {hint}")
            exit_code = 1
            continue
        print(f"== {item.repo.name}: pull ==")
        exit_code = run_git(item.repo.path, "pull", "--ff-only") or exit_code
    return exit_code


def do_sync(profile: str | None, start: Path | None) -> int:
    switch_code = do_switch(profile, start)
    pull_code = do_pull(profile, start)
    return switch_code or pull_code


def parse_exec_tokens(tokens: list[str], profiles: set[str]) -> tuple[str | None, list[str]]:
    if not tokens:
        return None, []
    if tokens[0] == "--":
        return None, tokens[1:]
    if "--" in tokens:
        separator = tokens.index("--")
        before = tokens[:separator]
        if len(before) > 1:
            raise ValueError("exec accepts at most one profile before --")
        return (before[0] if before else None), tokens[separator + 1 :]
    if tokens[0] in profiles:
        return tokens[0], tokens[1:]
    return None, tokens


def do_exec(tokens: list[str], start: Path | None) -> int:
    workspace = load_workspace(start)
    try:
        profile, command_tokens = parse_exec_tokens(tokens, set(workspace.config.profiles))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    command = " ".join(command_tokens).strip()
    if not command:
        print("gws exec requires a command", file=sys.stderr)
        return 2

    selected = plan_items_for_action(
        workspace,
        profile,
        {"pull", "checkout + pull", "skip pull", "blocked"},
    )
    repos = [item.repo for item in selected] or list(workspace.repos)
    exit_code = 0
    for repo in repos:
        print(f"== {repo.name} ==", flush=True)
        resolved = resolve_command(command, repo, workspace.config, ExecMode.SHELL)
        if resolved is None:
            continue
        proc = subprocess.run(resolved.args, cwd=str(resolved.cwd), text=True, env=process_env())
        exit_code = proc.returncode or exit_code
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command

    if command is None or command == "tui":
        GitWorkspace(args.cwd).run()
        return 0

    workspace = load_workspace(args.cwd)
    if command in {"status", "st", "s"}:
        print_status(workspace, args.profile)
        return 0
    if command == "plan":
        print_plan(workspace, args.profile)
        return 0
    if command == "switch":
        return do_switch(args.profile, args.cwd)
    if command == "pull":
        return do_pull(args.profile, args.cwd)
    if command == "sync":
        return do_sync(args.profile, args.cwd)
    if command == "exec":
        return do_exec(args.tokens, args.cwd)
    parser.print_help()
    return 2
