from __future__ import annotations

import asyncio
from pathlib import Path

from conftest import init_repo

from git_workspace.models import ExecMode
from git_workspace.tui import GitWorkspace, Input, RepoTable


async def _make_app(tmp_path: Path) -> GitWorkspace:
    init_repo(tmp_path / "api")
    init_repo(tmp_path / "web")
    return GitWorkspace(tmp_path)


def test_tui_input_switch_and_mode(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", Input)
            table = app.query_one("#repo-table", RepoTable)
            assert app.focused is cmd
            assert table.cursor_row == 0
            await pilot.press("p", "w", "d")
            assert cmd.value == "pwd"
            start_row = table.cursor_row
            await pilot.press("tab")
            await pilot.pause(0.1)
            assert table.cursor_row == (start_row + 1) % 3
            assert cmd.value == "pwd"
            await pilot.press("shift+tab")
            await pilot.pause(0.1)
            assert table.cursor_row == start_row
            await pilot.press("shift+tab")
            await pilot.pause(0.1)
            assert table.cursor_row == 2
            await pilot.press("tab")
            await pilot.pause(0.1)
            assert table.cursor_row == 0
            cmd.value = ":git"
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert app.exec_mode == ExecMode.GIT
            cmd.value = ":shell"
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert app.exec_mode == ExecMode.SHELL
            app.exit()

    asyncio.run(run())


def test_tui_alternate_repo_keys_and_ctrl_q(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            table = app.query_one("#repo-table", RepoTable)
            assert table.cursor_row == 0
            await pilot.press("ctrl+j")
            await pilot.pause(0.1)
            assert table.cursor_row == 1
            await pilot.press("ctrl+k")
            await pilot.pause(0.1)
            assert table.cursor_row == 0
            await pilot.press("ctrl+q")
            await pilot.pause(0.1)
            assert not app.is_running

    asyncio.run(run())


def test_tui_ctrl_c_cancels_running_command(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", Input)
            cmd.value = "sleep 5"
            await pilot.press("enter")
            await pilot.pause(0.6)
            assert app.command_running
            await pilot.press("ctrl+c")
            await pilot.pause(1.0)
            assert not app.command_running
            assert app.is_running
            app.exit()

    asyncio.run(run())


def test_tui_all_scope_runs_all_repos_and_keeps_input(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", Input)
            table = app.query_one("#repo-table", RepoTable)
            assert table.cursor_row == 0
            cmd.value = "sleep 0.3"
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert app.command_running
            assert len(app.batch_queue) in {0, 1}
            cmd.value = "sleep 0.3"
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert len(app.batch_queue) in {0, 1}
            assert app.focused is cmd
            await pilot.press("ctrl+c")
            await pilot.pause(0.5)
            assert not app.command_running
            assert not app.batch_queue
            assert app.focused is cmd
            app.exit()

    asyncio.run(run())


def test_tui_repo_scope_still_works_for_single_repo(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            table = app.query_one("#repo-table", RepoTable)
            cmd = app.query_one("#cmd", Input)
            await pilot.press("tab")
            await pilot.pause(0.1)
            assert table.cursor_row == 1
            cmd.value = "pwd"
            await pilot.press("enter")
            await pilot.pause(0.6)
            assert not app.command_running
            assert app.focused is cmd
            app.exit()

    asyncio.run(run())
