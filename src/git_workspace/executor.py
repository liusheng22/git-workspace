from __future__ import annotations

import os
import shlex
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .git import git_aliases
from .models import ExecMode, Repo, WorkspaceConfig

BUILTIN_GIT_ALIASES: dict[str, str] = {
    "g": "status -sb",
    "gs": "status -sb",
    "gst": "status -sb",
    "gss": "status -s",
    "ga": "add",
    "gaa": "add --all",
    "gb": "branch",
    "gba": "branch -a",
    "gbr": "branch --remote",
    "gco": "checkout",
    "gcb": "checkout -b",
    "gsw": "switch",
    "gswc": "switch -c",
    "gd": "diff",
    "gds": "diff --stat",
    "gf": "fetch --all --prune",
    "gl": "pull",
    "gp": "push",
    "gpl": "pull",
    "gps": "push",
    "glog": "log --oneline --decorate -20",
    "grv": "remote -v",
}


@dataclass(frozen=True)
class ResolvedCommand:
    display: str
    args: list[str]
    cwd: Path
    shell_mode: bool
    expanded: str | None = None


def normalize_git_command(command: str) -> str:
    command = command.strip()
    if command.startswith("git "):
        return command[4:].strip()
    return command


def shell_program() -> str:
    return os.environ.get("SHELL") or "/bin/sh"


def _source_if_readable(path: str) -> str:
    return f'[ -r "{path}" ] && . "{path}" >/dev/null 2>&1 || true'


def _posix_shell_script(command: str, shell_name: str) -> str:
    rc_files: tuple[str, ...]
    prelude: list[str] = ["set +e"]
    if shell_name == "zsh":
        prelude.append("setopt aliases >/dev/null 2>&1 || true")
        rc_files = ("$HOME/.zshenv", "$HOME/.zprofile", "$HOME/.zshrc")
    elif shell_name == "bash":
        prelude.append("shopt -s expand_aliases >/dev/null 2>&1 || true")
        rc_files = ("$HOME/.bash_profile", "$HOME/.bash_login", "$HOME/.profile", "$HOME/.bashrc")
    elif shell_name == "ksh":
        rc_files = ("$HOME/.profile", "$HOME/.kshrc")
    else:
        rc_files = ()

    lines = [f"GWS_COMMAND={shlex.quote(command)}", *prelude]
    lines.extend(_source_if_readable(path) for path in rc_files)
    lines.append("set +e")
    lines.append('eval "$GWS_COMMAND"')
    return "\n".join(lines)


def shell_invocation(command: str, interactive: bool = True) -> list[str]:
    shell = shell_program()
    name = Path(shell).name
    if interactive and name in {"bash", "zsh", "ksh"}:
        flag = "-fc" if name == "zsh" else "-c"
        return [shell, flag, _posix_shell_script(command, name)]
    if interactive and name == "fish":
        return [shell, "-ic", command]
    return [shell, "-lc", command]


def command_exists_in_shell(command: str, cwd: Path, interactive: bool = True) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return True
    if not parts:
        return False
    head = parts[0]
    if head.startswith(":") or head in {"cd", "export", "alias", "unalias", "source", "."}:
        return True
    probe = f"type {shlex.quote(head)} >/dev/null 2>&1"
    try:
        proc = subprocess.run(
            shell_invocation(probe, interactive=interactive),
            cwd=str(cwd),
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except Exception:
        return True
    return proc.returncode == 0


def aliases_for_repo(config: WorkspaceConfig, repo: Repo) -> dict[str, str]:
    aliases: dict[str, str] = {}
    aliases.update(BUILTIN_GIT_ALIASES)
    aliases.update(git_aliases(repo))
    aliases.update(config.aliases)
    return aliases


def expand_git_alias(command: str, aliases: dict[str, str]) -> tuple[str, bool]:
    command = normalize_git_command(command)
    try:
        parts = shlex.split(command)
    except ValueError:
        return command, False
    if not parts:
        return "", False
    head = parts[0]
    expansion = aliases.get(head)
    if expansion is None:
        return command, False
    rest = " ".join(shlex.quote(part) for part in parts[1:])
    expanded = f"{expansion} {rest}".strip()
    return normalize_git_command(expanded), expanded != command


def resolve_command(
    value: str,
    repo: Repo,
    config: WorkspaceConfig,
    mode: ExecMode,
) -> ResolvedCommand | None:
    value = value.strip()
    if not value:
        return None

    interactive = config.exec_settings.interactive_shell

    if value.startswith("!"):
        command = value[1:].strip()
        if not command:
            return None
        return ResolvedCommand(value, shell_invocation(command, interactive), repo.path, True)

    if mode == ExecMode.SHELL:
        if command_exists_in_shell(value, repo.path, interactive):
            return ResolvedCommand(value, shell_invocation(value, interactive), repo.path, True)
        if not config.exec_settings.git_shortcuts:
            return ResolvedCommand(value, shell_invocation(value, interactive), repo.path, True)

    aliases = aliases_for_repo(config, repo)
    command, expanded = expand_git_alias(value, aliases)
    if not command:
        return None
    try:
        git_args = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"解析失败：{exc}") from exc
    return ResolvedCommand(
        value,
        ["git", "-C", str(repo.path), "--no-pager", *git_args],
        config.root,
        False,
        command if expanded or value.startswith("git ") else None,
    )


def process_env() -> dict[str, str]:
    env = os.environ.copy()
    term = os.environ.get("TERM") or "xterm-256color"
    if term == "dumb":
        term = "xterm-256color"
    env.update(
        {
            "GIT_PAGER": "cat",
            "PAGER": "cat",
            "LESS": "FRX",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_WORKSPACE": "1",
            "TERM": term,
        }
    )
    return env


def terminate_process(proc: subprocess.Popen[str]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        proc.terminate()
