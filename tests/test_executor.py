from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import init_repo

from git_workspace.config import load_config
from git_workspace.executor import process_env, resolve_command, shell_invocation
from git_workspace.models import ExecMode, Repo


def test_shell_mode_runs_shell_command(tmp_path: Path) -> None:
    repo_path = init_repo(tmp_path / "api")
    config = load_config(tmp_path)
    repo = Repo("api", repo_path)

    resolved = resolve_command("pwd", repo, config, ExecMode.SHELL)

    assert resolved is not None
    assert resolved.shell_mode
    assert resolved.cwd == repo_path


def test_shell_mode_falls_back_to_git_shortcut(tmp_path: Path) -> None:
    repo_path = init_repo(tmp_path / "api")
    (tmp_path / "workspace.yml").write_text(
        """
aliases:
  __gws_test_checkout__: checkout
""",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    repo = Repo("api", repo_path)

    resolved = resolve_command("__gws_test_checkout__ main", repo, config, ExecMode.SHELL)

    assert resolved is not None
    assert not resolved.shell_mode
    assert resolved.args[-2:] == ["checkout", "main"]


def test_git_mode_expands_builtin_alias(tmp_path: Path) -> None:
    repo_path = init_repo(tmp_path / "api")
    config = load_config(tmp_path)
    repo = Repo("api", repo_path)

    resolved = resolve_command("gl", repo, config, ExecMode.GIT)

    assert resolved is not None
    assert resolved.args[-1] == "pull"


def test_shell_invocation_loads_alias_without_rc_noise(tmp_path: Path, monkeypatch) -> None:
    repo_path = init_repo(tmp_path / "api")
    home = tmp_path / "home"
    home.mkdir()
    shell = shutil.which("zsh")
    rc_file = ".zshrc"
    if shell is None:
        shell = shutil.which("bash")
        rc_file = ".bashrc"
    if shell is None:
        pytest.skip("requires zsh or bash")

    (home / rc_file).write_text(
        """
echo noisy startup
alias __gws_alias_noise_test__='echo alias-ok'
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", shell)

    proc = subprocess.run(
        shell_invocation("__gws_alias_noise_test__", interactive=True),
        cwd=str(repo_path),
        env=process_env(),
        text=True,
        capture_output=True,
        check=True,
    )

    assert proc.stdout.strip() == "alias-ok"
    assert proc.stderr == ""
