from __future__ import annotations

from pathlib import Path

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
