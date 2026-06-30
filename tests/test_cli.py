from __future__ import annotations

from pathlib import Path

import pytest

from git_workspace import cli


class DummyTui:
    calls: list[dict[str, object]] = []

    def __init__(self, start: Path | None = None) -> None:
        self.start = start

    def run(self, **kwargs: object) -> None:
        self.calls.append({"start": self.start, **kwargs})


def test_tui_runs_without_mouse_capture(monkeypatch) -> None:
    DummyTui.calls.clear()
    monkeypatch.setattr(cli, "GitWorkspace", DummyTui)

    assert cli.main(["tui"]) == 0

    assert DummyTui.calls == [{"start": None, "mouse": False}]


def test_default_command_runs_tui_without_mouse_capture(monkeypatch, tmp_path: Path) -> None:
    DummyTui.calls.clear()
    monkeypatch.setattr(cli, "GitWorkspace", DummyTui)

    assert cli.main(["--cwd", str(tmp_path)]) == 0

    assert DummyTui.calls == [{"start": tmp_path, "mouse": False}]


def test_version_option_prints_package_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("gws ")


def test_update_uses_uv_tool_upgrade(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/bin/{name}" if name == "uv" else None)
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command) or type("Proc", (), {"returncode": 0})(),
    )

    assert cli.main(["update"]) == 0
    assert calls == [["/bin/uv", "tool", "upgrade", "git-workspace-tui"]]


def test_update_force_uses_uv_tool_install_force(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/bin/{name}" if name == "uv" else None)
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command) or type("Proc", (), {"returncode": 0})(),
    )

    assert cli.main(["self", "update", "--force"]) == 0
    assert calls == [["/bin/uv", "tool", "install", "--force", "git-workspace-tui"]]


def test_update_falls_back_to_pipx(monkeypatch) -> None:
    calls: list[list[str]] = []

    def which(name: str) -> str | None:
        return "/bin/pipx" if name == "pipx" else None

    monkeypatch.setattr(cli.shutil, "which", which)
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command) or type("Proc", (), {"returncode": 0})(),
    )

    assert cli.main(["update"]) == 0
    assert calls == [["/bin/pipx", "upgrade", "git-workspace-tui"]]


def test_update_reports_missing_tool(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)

    assert cli.main(["update"]) == 1
    assert "requires uv or pipx" in capsys.readouterr().err
