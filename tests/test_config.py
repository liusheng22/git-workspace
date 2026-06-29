from __future__ import annotations

from pathlib import Path

from git_workspace.config import load_config
from git_workspace.models import ExecMode


def test_load_workspace_config(tmp_path: Path) -> None:
    (tmp_path / "workspace.yml").write_text(
        """
workspace:
  root: .
  ignore:
    - node_modules
repos:
  api:
    path: ./api
    default: main
profiles:
  daily:
    api: dev
aliases:
  gco: checkout
exec:
  defaultMode: git
  gitShortcuts: false
  shell:
    loadRc: true
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.root == tmp_path
    assert config.ignore == ("node_modules",)
    assert config.repos["api"]["default"] == "main"
    assert config.profiles["daily"]["api"] == "dev"
    assert config.aliases["gco"] == "checkout"
    assert config.exec_settings.default_mode == ExecMode.GIT
    assert not config.exec_settings.git_shortcuts
    assert config.exec_settings.load_shell_rc


def test_shell_rc_loading_uses_runtime_default_when_not_configured(tmp_path: Path) -> None:
    config = load_config(tmp_path)

    assert config.exec_settings.load_shell_rc is None


def test_legacy_interactive_shell_config_does_not_load_rc(tmp_path: Path) -> None:
    (tmp_path / "workspace.yml").write_text(
        """
exec:
  shell:
    interactive: true
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.exec_settings.load_shell_rc is None


def test_local_config_overrides(tmp_path: Path) -> None:
    (tmp_path / "workspace.yml").write_text(
        """
exec:
  defaultMode: git
""",
        encoding="utf-8",
    )
    (tmp_path / "workspace.local.yml").write_text(
        """
exec:
  defaultMode: shell
""",
        encoding="utf-8",
    )

    assert load_config(tmp_path).exec_settings.default_mode == ExecMode.SHELL
