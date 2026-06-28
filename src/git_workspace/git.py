from __future__ import annotations

import subprocess
from pathlib import Path

from .models import Repo, RepoState


def git(repo: Path, *args: str, timeout: float | None = 12) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            exc.cmd,
            124,
            exc.stdout if isinstance(exc.stdout, str) else "",
            exc.stderr if isinstance(exc.stderr, str) else "timeout",
        )


def is_git_worktree(path: Path) -> bool:
    result = git(path, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def git_toplevel(path: Path) -> Path | None:
    result = git(path, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return Path(value).resolve() if value else None


def current_branch(repo: Path) -> str:
    result = git(repo, "branch", "--show-current")
    value = result.stdout.strip()
    if value:
        return value
    result = git(repo, "rev-parse", "--short", "HEAD")
    return f"detached:{result.stdout.strip() or '?'}"


def dirty_count(repo: Path) -> int:
    result = git(repo, "status", "--porcelain=v1")
    return len([line for line in result.stdout.splitlines() if line.strip()])


def upstream(repo: Path) -> str | None:
    result = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value if value and value != "@{u}" else None


def ahead_behind(repo: Path, upstream_ref: str) -> tuple[int, int] | tuple[None, None]:
    result = git(repo, "rev-list", "--left-right", "--count", f"{upstream_ref}...HEAD")
    if result.returncode != 0:
        return None, None
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        return None, None
    behind, ahead = parts
    return int(ahead), int(behind)


def repo_state(repo: Repo) -> RepoState:
    up = upstream(repo.path)
    ahead: int | None = None
    behind: int | None = None
    if up:
        ahead, behind = ahead_behind(repo.path, up)
    return RepoState(
        branch=current_branch(repo.path),
        dirty=dirty_count(repo.path),
        upstream=up,
        ahead=ahead,
        behind=behind,
    )


def git_aliases(repo: Repo | None = None) -> dict[str, str]:
    args = ["git"]
    if repo is not None:
        args.extend(["-C", str(repo.path)])
    args.extend(["config", "--get-regexp", r"^alias\."])
    proc = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    aliases: dict[str, str] = {}
    if proc.returncode not in {0, 1}:
        return aliases
    for raw in proc.stdout.splitlines():
        key, _, value = raw.partition(" ")
        if not key.startswith("alias.") or not value.strip():
            continue
        aliases[key.removeprefix("alias.")] = value.strip()
    return aliases
