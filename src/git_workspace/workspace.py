from __future__ import annotations

import fnmatch
from pathlib import Path

from .config import load_config
from .git import git_toplevel, is_git_worktree
from .models import Repo, Workspace, WorkspaceConfig


def _ignored(path: Path, root: Path, patterns: tuple[str, ...]) -> bool:
    rel = path.relative_to(root).as_posix()
    name = path.name
    return any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _repo_from_path(name: str, path: Path, default_branch: str = "main") -> Repo | None:
    resolved = path.resolve()
    if not resolved.exists() or not resolved.is_dir() or not is_git_worktree(resolved):
        return None
    top = git_toplevel(resolved)
    if top is None:
        return None
    return Repo(name=name, path=top, default_branch=default_branch)


def discover_repos(config: WorkspaceConfig) -> tuple[Repo, ...]:
    by_path: dict[Path, Repo] = {}

    for name, data in config.repos.items():
        raw_path = data.get("path", f"./{name}")
        path = (config.root / raw_path).resolve()
        repo = _repo_from_path(name, path, data.get("default", "main"))
        if repo is not None:
            by_path[repo.path] = repo

    if not config.repos and config.root.exists():
        for path in sorted(config.root.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_dir() or _ignored(path, config.root, config.ignore):
                continue
            repo = _repo_from_path(path.name, path)
            if repo is not None and repo.path == path.resolve():
                by_path[repo.path] = repo

    return tuple(sorted(by_path.values(), key=lambda repo: repo.name.lower()))


def load_workspace(start: Path | None = None) -> Workspace:
    config = load_config(start)
    return Workspace(config=config, repos=discover_repos(config))

