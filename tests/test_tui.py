from __future__ import annotations

import asyncio
from pathlib import Path

from conftest import init_repo, run
from textual import events
from textual.widgets import Static
from textual.widgets._header import HeaderClock, HeaderIcon

from git_workspace.models import ExecMode
from git_workspace.tui import CommandInput, GitWorkspace, RepoTable


async def _make_app(tmp_path: Path) -> GitWorkspace:
    init_repo(tmp_path / "api")
    init_repo(tmp_path / "web")
    return GitWorkspace(tmp_path)


def test_tui_input_switch_and_mode(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            table = app.query_one("#repo-table", RepoTable)
            assert app.focused is cmd
            assert table.cursor_row == 0
            await pilot.press("p", "w", "d")
            assert cmd.text == "pwd"
            start_row = table.cursor_row
            await pilot.press("tab")
            await pilot.pause(0.1)
            assert table.cursor_row == (start_row + 1) % 3
            assert cmd.text == "pwd"
            await pilot.press("shift+tab")
            await pilot.pause(0.1)
            assert table.cursor_row == start_row
            await pilot.press("shift+tab")
            await pilot.pause(0.1)
            assert table.cursor_row == 2
            await pilot.press("tab")
            await pilot.pause(0.1)
            assert table.cursor_row == 0
            cmd.text = ":git"
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert app.exec_mode == ExecMode.GIT
            cmd.text = ":shell"
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert app.exec_mode == ExecMode.SHELL
            app.exit()

    asyncio.run(run())


def test_tui_repo_context_shows_branch_label(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            await pilot.press("tab")
            await pilot.pause(0.1)
            title = app.query_one("#exec-title", Static)
            assert title.render().plain == "SHELL api  branch main  clean"
            app.exit()

    asyncio.run(run())


def test_tui_repo_context_shows_sync_badge(tmp_path: Path) -> None:
    async def run_test() -> None:
        remote = tmp_path / "remote.git"
        remote.mkdir()
        run(["git", "init", "--bare"], remote)

        repo = init_repo(tmp_path / "api")
        run(["git", "remote", "add", "origin", str(remote)], repo)
        run(["git", "push", "-u", "origin", "main"], repo)
        (repo / "local.txt").write_text("local\n", encoding="utf-8")
        run(["git", "add", "local.txt"], repo)
        run(["git", "commit", "-m", "local"], repo)

        other = tmp_path / "other"
        run(["git", "clone", str(remote), str(other)], tmp_path)
        run(["git", "config", "user.email", "test@example.com"], other)
        run(["git", "config", "user.name", "Test User"], other)
        (other / "remote.txt").write_text("remote\n", encoding="utf-8")
        run(["git", "add", "remote.txt"], other)
        run(["git", "commit", "-m", "remote"], other)
        run(["git", "push"], other)
        run(["git", "fetch", "origin"], repo)

        app = GitWorkspace(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            await pilot.press("tab")
            await pilot.pause(0.1)
            title = app.query_one("#exec-title", Static)
            assert "branch main  ↑1  ↓1  clean" in title.render().plain
            app.exit()

    asyncio.run(run_test())


def test_tui_footer_uses_macos_friendly_page_key_labels() -> None:
    bindings = [binding for binding in GitWorkspace.BINDINGS if not isinstance(binding, tuple)]
    by_action = {binding.action: binding for binding in bindings}

    assert by_action["log_page_up"].key == "pageup"
    assert by_action["log_page_up"].key_display == "fn+↑"
    assert by_action["log_page_down"].key == "pagedown"
    assert by_action["log_page_down"].key_display == "fn+↓"


def test_tui_shift_enter_inserts_newline_and_enter_submits(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            table = app.query_one("#repo-table", RepoTable)
            assert table.cursor_row == 0
            app.exec_mode = ExecMode.SHELL
            await pilot.press("tab")
            await pilot.pause(0.1)
            assert table.cursor_row == 1
            started: list[tuple[str, ExecMode]] = []

            def fake_start_command(repo, value: str, mode: ExecMode) -> None:
                started.append((value, mode))

            app.start_command = fake_start_command  # type: ignore[method-assign]

            await pilot.press("p", "w", "d", "shift+enter", "p", "w", "d")
            await pilot.pause(0.1)
            assert cmd.text == "pwd\npwd"

            await pilot.press("enter")
            await pilot.pause(0.1)
            assert cmd.text == ""
            assert started == [("pwd\npwd", ExecMode.SHELL)]
            assert app.history[-1] == "pwd\npwd"
            app.exit()

    asyncio.run(run())


def test_command_input_accepts_shift_carriage_return(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            cmd = app.query_one("#cmd", CommandInput)
            cmd.text = "pwd"
            cmd.move_cursor(cmd.document.end)
            await cmd._on_key(events.Key("shift+\r", None))
            assert cmd.text == "pwd\n"
            app.exit()

    asyncio.run(run())


def test_tui_multiline_arrows_move_inside_input_before_history(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            app.history = ["git status"]
            cmd.text = "first\nsecond"
            cmd.move_cursor(cmd.document.end)

            await pilot.press("up")
            await pilot.pause(0.1)
            assert cmd.text == "first\nsecond"
            assert cmd.cursor_location[0] == 0

            await pilot.press("up")
            await pilot.pause(0.1)
            assert cmd.text == "git status"
            app.exit()

    asyncio.run(run())


def test_tui_git_mode_multiline_submits_each_line(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            table = app.query_one("#repo-table", RepoTable)
            app.exec_mode = ExecMode.GIT
            await pilot.press("tab")
            await pilot.pause(0.1)
            assert table.cursor_row == 1
            started: list[tuple[str, ExecMode]] = []

            def fake_start_command(repo, value: str, mode: ExecMode) -> None:
                started.append((value, mode))

            app.start_command = fake_start_command  # type: ignore[method-assign]

            cmd.text = "status --short\nbranch --show-current"
            cmd.move_cursor(cmd.document.end)
            await pilot.press("enter")
            await pilot.pause(0.1)

            assert started == [
                ("status --short", ExecMode.GIT),
                ("branch --show-current", ExecMode.GIT),
            ]
            app.exit()

    asyncio.run(run())


def test_tui_key_debug_toggle_and_records_input(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            debug = app.key_debug
            assert not app.key_debug_enabled
            assert "-enabled" not in debug.classes

            cmd.text = ":keys"
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert app.key_debug_enabled
            assert "-enabled" in debug.classes

            app.record_raw_input(b"\x1b[13;2u", "\x1b[13;2u")
            app.record_key_event("shift+enter", None, None, False)
            assert app.key_debug_state.raw_hex == "1b 5b 31 33 3b 32 75"
            assert app.key_debug_state.key == "shift+enter"
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


def test_tui_mount_has_no_ready_noise(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            assert "Git Workspace ready" not in str(app.exec_log.lines)
            app.exit()

    asyncio.run(run())


def test_tui_header_does_not_refresh_clock(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            assert not app.query(HeaderClock)
            app.exit()

    asyncio.run(run())


def test_tui_header_hides_default_icon(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            icon = app.query_one(HeaderIcon)
            assert icon.styles.display == "none"
            assert icon.styles.width.value == 0
            app.exit()

    asyncio.run(run())


def test_tui_input_cursor_does_not_blink(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            assert cmd.cursor_blink is False
            assert cmd.blink_timer is not None
            assert not cmd.blink_timer._active.is_set()
            app.exit()

    asyncio.run(run())


def test_tui_ctrl_c_cancels_running_command(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            cmd.text = "sleep 5"
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
            cmd = app.query_one("#cmd", CommandInput)
            table = app.query_one("#repo-table", RepoTable)
            assert table.cursor_row == 0
            cmd.text = "sleep 0.3"
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert app.command_running
            assert len(app.batch_queue) in {0, 1}
            cmd.text = "sleep 0.3"
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


def test_tui_all_scope_copies_whole_batch_and_runs_first_repo(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        (tmp_path / "api" / "api.txt").write_text("api\n", encoding="utf-8")
        (tmp_path / "web" / "web.txt").write_text("web\n", encoding="utf-8")
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            app.exec_mode = ExecMode.GIT
            cmd.text = "status --short"
            await pilot.press("enter")
            await pilot.pause(1.2)
            assert not app.command_running
            text = str(app.exec_log.lines)
            assert "scope: ALL (2 repos)" in text
            assert "api" in text
            assert "api.txt" in text
            assert "web" in text
            assert "web.txt" in text
            assert "ALL completed  (2 repos)" in text
            app.exit()

    asyncio.run(run())


def test_tui_clear_log_clears_output(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            app.write_log("older output")
            assert app.exec_log.lines
            app.action_clear_log()
            assert not app.exec_log.lines
            app.exit()

    asyncio.run(run())


def test_tui_page_keys_scroll_log_and_keep_input_focused(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 12)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            log = app.exec_log
            for index in range(80):
                app.write_log(f"line {index}")
            await pilot.pause(0.2)
            assert app.focused is cmd
            bottom = log.scroll_y
            await pilot.press("pageup")
            await pilot.pause(0.1)
            assert log.scroll_y < bottom
            assert app.focused is cmd
            await pilot.press("pagedown")
            await pilot.pause(0.1)
            assert log.scroll_y >= bottom
            assert app.focused is cmd
            app.exit()

    asyncio.run(run())


def test_tui_repo_scope_still_works_for_single_repo(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            table = app.query_one("#repo-table", RepoTable)
            cmd = app.query_one("#cmd", CommandInput)
            await pilot.press("tab")
            await pilot.pause(0.1)
            assert table.cursor_row == 1
            cmd.text = "pwd"
            await pilot.press("enter")
            await pilot.pause(0.6)
            assert not app.command_running
            assert app.focused is cmd
            app.exit()

    asyncio.run(run())
