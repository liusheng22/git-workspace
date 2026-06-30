from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import init_repo

from git_workspace.config import load_config
from git_workspace.executor import RC_STATUS_PREFIX, process_env, resolve_command, shell_invocation
from git_workspace.models import ExecMode, Repo


def test_shell_mode_runs_shell_command(tmp_path: Path) -> None:
    repo_path = init_repo(tmp_path / "api")
    config = load_config(tmp_path)
    repo = Repo("api", repo_path)

    resolved = resolve_command("pwd", repo, config, ExecMode.SHELL)

    assert resolved is not None
    assert resolved.shell_mode
    assert resolved.cwd == repo_path


def test_shell_invocation_does_not_load_rc_files_by_default(tmp_path: Path, monkeypatch) -> None:
    shell = shutil.which("zsh") or shutil.which("bash")
    if shell is None:
        pytest.skip("requires zsh or bash")

    home = tmp_path / "home"
    marker = tmp_path / "rc-loaded"
    home.mkdir()
    (home / ".zshrc").write_text(f"touch {shlex.quote(str(marker))}\n", encoding="utf-8")
    (home / ".bashrc").write_text(f"touch {shlex.quote(str(marker))}\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", shell)

    proc = subprocess.run(
        shell_invocation("echo ok"),
        cwd=str(tmp_path),
        env=process_env(),
        text=True,
        capture_output=True,
        check=True,
    )

    assert proc.stdout.strip() == "ok"
    assert not marker.exists()


def test_process_env_strips_non_interactive_shell_startup_by_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("requires bash")

    marker = tmp_path / "bash-env-loaded"
    bash_env = tmp_path / "bash-env"
    bash_env.write_text(f"touch {shlex.quote(str(marker))}\n", encoding="utf-8")
    monkeypatch.setenv("SHELL", shell)
    monkeypatch.setenv("BASH_ENV", str(bash_env))

    subprocess.run(
        shell_invocation("echo ok"),
        cwd=str(tmp_path),
        env=process_env(),
        text=True,
        capture_output=True,
        check=True,
    )

    assert not marker.exists()


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


def test_shell_rc_loading_requires_explicit_config(tmp_path: Path, monkeypatch) -> None:
    repo_path = init_repo(tmp_path / "api")
    home = tmp_path / "home"
    marker = tmp_path / "rc-loaded"
    home.mkdir()
    (home / ".zshrc").write_text(f"touch {shlex.quote(str(marker))}\n", encoding="utf-8")
    (home / ".bashrc").write_text(f"touch {shlex.quote(str(marker))}\n", encoding="utf-8")
    (tmp_path / "workspace.yml").write_text(
        """
exec:
  shell:
    loadRc: true
""",
        encoding="utf-8",
    )
    shell = shutil.which("zsh") or shutil.which("bash")
    if shell is None:
        pytest.skip("requires zsh or bash")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", shell)

    config = load_config(tmp_path)
    repo = Repo("api", repo_path)

    resolved = resolve_command("echo ok", repo, config, ExecMode.SHELL)

    assert resolved is not None
    subprocess.run(
        resolved.args,
        cwd=str(resolved.cwd),
        env=process_env(),
        text=True,
        capture_output=True,
        check=True,
    )
    assert marker.exists()


def test_tui_runtime_default_loads_shell_rc(tmp_path: Path, monkeypatch) -> None:
    repo_path = init_repo(tmp_path / "api")
    home = tmp_path / "home"
    marker = tmp_path / "tui-rc-loaded"
    home.mkdir()
    (home / ".zshrc").write_text(f"touch {shlex.quote(str(marker))}\n", encoding="utf-8")
    (home / ".bashrc").write_text(f"touch {shlex.quote(str(marker))}\n", encoding="utf-8")
    shell = shutil.which("zsh") or shutil.which("bash")
    if shell is None:
        pytest.skip("requires zsh or bash")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", shell)

    config = load_config(tmp_path)
    repo = Repo("api", repo_path)

    resolved = resolve_command("echo ok", repo, config, ExecMode.SHELL, load_shell_rc=True)

    assert resolved is not None
    subprocess.run(
        resolved.args,
        cwd=str(resolved.cwd),
        env=process_env(load_shell_rc=True),
        text=True,
        capture_output=True,
        check=True,
    )
    assert marker.exists()


def test_explicit_config_disables_tui_runtime_rc_default(tmp_path: Path, monkeypatch) -> None:
    repo_path = init_repo(tmp_path / "api")
    home = tmp_path / "home"
    marker = tmp_path / "tui-rc-loaded"
    home.mkdir()
    (home / ".zshrc").write_text(f"touch {shlex.quote(str(marker))}\n", encoding="utf-8")
    (home / ".bashrc").write_text(f"touch {shlex.quote(str(marker))}\n", encoding="utf-8")
    (tmp_path / "workspace.yml").write_text(
        """
exec:
  shell:
    loadRc: false
""",
        encoding="utf-8",
    )
    shell = shutil.which("zsh") or shutil.which("bash")
    if shell is None:
        pytest.skip("requires zsh or bash")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", shell)

    config = load_config(tmp_path)
    repo = Repo("api", repo_path)

    resolved = resolve_command("echo ok", repo, config, ExecMode.SHELL, load_shell_rc=True)

    assert resolved is not None
    subprocess.run(
        resolved.args,
        cwd=str(resolved.cwd),
        env=process_env(load_shell_rc=False),
        text=True,
        capture_output=True,
        check=True,
    )
    assert not marker.exists()


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
        shell_invocation("__gws_alias_noise_test__", load_rc=True),
        cwd=str(repo_path),
        env=process_env(),
        text=True,
        capture_output=True,
        check=True,
    )

    assert proc.stdout.strip() == "alias-ok"
    assert proc.stderr == ""


def test_shell_invocation_reports_rc_status_when_requested(tmp_path: Path, monkeypatch) -> None:
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

    (home / rc_file).write_text("alias __gws_status_test__='echo ok'\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", shell)

    proc = subprocess.run(
        shell_invocation("__gws_status_test__", load_rc=True),
        cwd=str(repo_path),
        env=process_env(load_shell_rc=True, report_shell_rc=True),
        text=True,
        capture_output=True,
        check=True,
    )

    lines = proc.stdout.splitlines()
    assert lines[0].startswith(RC_STATUS_PREFIX)
    assert f"{home / rc_file}:0" in lines[0]
    assert lines[-1] == "ok"


@pytest.mark.parametrize("rc_body", ["exit 42\n", "return 33\n", "if then\n"])
def test_shell_rc_errors_do_not_block_command(tmp_path: Path, monkeypatch, rc_body: str) -> None:
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

    (home / rc_file).write_text(rc_body, encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", shell)

    proc = subprocess.run(
        shell_invocation("echo command-ok", load_rc=True),
        cwd=str(repo_path),
        env=process_env(load_shell_rc=True),
        text=True,
        capture_output=True,
        check=True,
    )

    assert proc.stdout.strip() == "command-ok"
