from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ExecMode(StrEnum):
    SHELL = "shell"
    GIT = "git"


@dataclass(frozen=True)
class Repo:
    name: str
    path: Path
    default_branch: str = "main"

    @property
    def key(self) -> str:
        return str(self.path)


@dataclass(frozen=True)
class RepoState:
    branch: str
    dirty: int
    upstream: str | None = None
    ahead: int | None = None
    behind: int | None = None

    @property
    def dirty_label(self) -> str:
        return f"dirty:{self.dirty}" if self.dirty else "clean"

    @property
    def sync_label(self) -> str:
        if self.upstream is None:
            return "-"
        if self.ahead == 0 and self.behind == 0:
            return "ok"
        return f"+{self.ahead or 0}/-{self.behind or 0}"


@dataclass(frozen=True)
class PlanItem:
    repo: Repo
    current: str
    target: str
    dirty: int
    action: str
    note: str = ""


@dataclass(frozen=True)
class ExecSettings:
    default_mode: ExecMode = ExecMode.SHELL
    git_shortcuts: bool = True
    interactive_shell: bool = True


@dataclass(frozen=True)
class WorkspaceConfig:
    root: Path
    config_file: Path | None = None
    ignore: tuple[str, ...] = ()
    repos: dict[str, dict[str, str]] = field(default_factory=dict)
    profiles: dict[str, dict[str, str]] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    exec_settings: ExecSettings = field(default_factory=ExecSettings)


@dataclass(frozen=True)
class Workspace:
    config: WorkspaceConfig
    repos: tuple[Repo, ...]

    @property
    def root(self) -> Path:
        return self.config.root

