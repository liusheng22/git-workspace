from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from conftest import init_repo, run
from textual import events
from textual.widgets import Static
from textual.widgets._header import HeaderClock, HeaderIcon

from git_workspace.models import ExecMode
from git_workspace.tui import (
    BatchCommand,
    BatchResult,
    CommandInput,
    GitWorkspace,
    RcStatusMessage,
    RepoTable,
)


async def _make_app(tmp_path: Path) -> GitWorkspace:
    init_repo(tmp_path / "api")
    init_repo(tmp_path / "web")
    return GitWorkspace(tmp_path)


async def _wait_for_idle(app: GitWorkspace, pilot, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while app.command_running and asyncio.get_running_loop().time() < deadline:
        await pilot.pause(0.1)


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
            title_text = title.render().plain
            assert "SHELL api  branch main  clean" in title_text
            assert "shell:" in title_text
            assert "rc:" in title_text
            assert "copy: opt/alt-drag" in title_text
            app.exit()

    asyncio.run(run())


def test_tui_copy_help_command_explains_rectangular_selection(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        app.start_rc_probe = lambda: None  # type: ignore[method-assign]
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)

            app.handle_builtin_command(":copy-help")

            text = str(app.exec_log.lines)
            assert "copy right output" in text
            assert "Option/Alt + drag" in text
            assert "depends on your terminal" in text
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
        run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], remote)
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


def test_tui_starts_rc_probe_on_mount(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        called = False

        def fake_start_rc_probe() -> None:
            nonlocal called
            called = True

        app.start_rc_probe = fake_start_rc_probe  # type: ignore[method-assign]

        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            assert called
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
            await _wait_for_idle(app, pilot)
            assert not app.command_running
            assert app.is_running
            app.exit()

    asyncio.run(run())


def test_tui_all_scope_cancel_clears_batch_and_keeps_input(tmp_path: Path, monkeypatch) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        terminated: list[object] = []
        monkeypatch.setattr("git_workspace.tui.terminate_process", lambda proc: terminated.append(proc))

        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause(0.5)
            cmd = app.query_one("#cmd", CommandInput)
            table = app.query_one("#repo-table", RepoTable)
            assert table.cursor_row == 0
            proc = SimpleNamespace(pid=12345, poll=lambda: None)
            app.command_running = True
            app.current_process = proc  # type: ignore[assignment]
            app.current_batch = BatchCommand("sleep 0.3", ExecMode.SHELL, tuple(app.repos))
            app.batch_queue.append(BatchCommand("sleep 0.3", ExecMode.SHELL, tuple(app.repos)))
            assert app.focused is cmd

            canceled = app.cancel_current_command()

            assert canceled
            assert app.cancel_requested
            assert app.current_batch is None
            assert not app.batch_queue
            assert terminated == [proc]
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
            assert "ALL git › status --short completed" in text
            app.exit()

    asyncio.run(run())


def test_tui_batch_summary_records_failures_and_actions(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            app.last_batch_results = [
                BatchResult(app.repos[0], 0, 1.2, ""),
                BatchResult(app.repos[1], 1, 0.4, "exit 1"),
            ]

            app.write_batch_summary(app.last_batch_results, "ALL shell › git pull")
            text = str(app.exec_log.lines)

            assert "ALL shell › git pull completed" in text
            assert "ok:1" in text
            assert "failed:1" in text
            assert ":failed" in text
            assert ":retry-failed" in text
            assert ":copy-failed" in text
            assert ":jump <repo>" in text
            assert app.repos[0].name in text
            assert app.repos[1].name in text
            assert "exit 1" in text
            app.exit()

    asyncio.run(run())


def test_tui_failed_summary_and_retry_failed(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        started: list[tuple[str, tuple[str, ...], ExecMode]] = []

        def fake_start_command(repo, value: str, mode: ExecMode) -> None:
            assert app.current_batch is not None
            started.append((value, tuple(item.name for item in app.current_batch.repos), mode))

        app.start_command = fake_start_command  # type: ignore[method-assign]

        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            app.last_batch_value = "git pull"
            app.last_batch_mode = ExecMode.SHELL
            app.last_batch_results = [
                BatchResult(app.repos[0], 0, 1.2, ""),
                BatchResult(app.repos[1], 1, 0.4, "exit 1"),
            ]

            app.write_failed_summary()
            app.retry_failed_repos()

            text = str(app.exec_log.lines)
            assert "failed repos completed" in text
            assert app.repos[1].name in text
            assert started == [("git pull", (app.repos[1].name,), ExecMode.SHELL)]
            app.exit()

    asyncio.run(run())


def test_tui_queued_failed_retry_keeps_failed_scope_label(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            app.command_running = True
            app.last_batch_value = "git pull"
            app.last_batch_mode = ExecMode.SHELL
            app.last_batch_results = [BatchResult(app.repos[1], 1, 0.4, "conflict")]

            app.retry_failed_repos()

            assert len(app.batch_queue) == 1
            queued = app.batch_queue[0]
            assert queued.scope == "FAILED retry"
            assert tuple(repo.name for repo in queued.repos) == (app.repos[1].name,)
            text = str(app.exec_log.lines)
            assert "queued: FAILED retry shell › git pull" in text
            app.exit()

    asyncio.run(run())


def test_tui_failed_scope_runs_next_command_only_on_failed_repos(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        started: list[tuple[str, tuple[str, ...], ExecMode]] = []

        def fake_start_command(repo, value: str, mode: ExecMode) -> None:
            assert app.current_batch is not None
            started.append((value, tuple(item.name for item in app.current_batch.repos), mode))

        app.start_command = fake_start_command  # type: ignore[method-assign]

        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            app.last_batch_value = "git pull"
            app.last_batch_mode = ExecMode.SHELL
            app.last_batch_results = [
                BatchResult(app.repos[0], 0, 1.2, ""),
                BatchResult(app.repos[1], 1, 0.4, "local changes"),
            ]

            app.activate_failed_scope()
            assert app.selected_target.scope == "failed"

            app.submit_command("git status -sb")

            assert started == [("git status -sb", (app.repos[1].name,), ExecMode.SHELL)]
            assert app.current_batch is not None
            assert app.current_batch.scope == "FAILED"
            app.exit()

    asyncio.run(run())


def test_tui_all_failures_do_not_implicitly_change_target(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            app.current_batch = BatchCommand("git pull", ExecMode.SHELL, tuple(app.repos), "ALL")
            app.current_batch_index = len(app.repos) - 1
            app.current_batch_results = [BatchResult(app.repos[0], 1, 0.4, "conflict")]

            app.run_next_queued()

            assert app.last_failed_repos == (app.repos[0],)
            assert app.failure_scope is None
            assert app.selected_target.is_all
            app.exit()

    asyncio.run(run())


def test_tui_copy_failed_summary_to_clipboard(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            app.last_batch_results = [
                BatchResult(app.repos[0], 0, 1.2, ""),
                BatchResult(app.repos[1], 1, 0.4, "conflict"),
            ]

            app.copy_failed_summary()

            assert "failed repos completed" in app.clipboard
            assert app.repos[1].name in app.clipboard
            assert "conflict" in app.clipboard
            assert app.repos[0].name not in app.clipboard
            app.exit()

    asyncio.run(run())


def test_tui_jump_to_repo_output_selects_repo_and_scrolls(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 12)):
            await asyncio.sleep(0.5)
            for index in range(40):
                app.write_log(f"line {index}")
            app.repo_log_positions[app.repos[1].key] = 25

            app.jump_to_repo_output(app.repos[1].name)

            assert app.repo_table.cursor_row == 2
            assert app.failure_scope is None
            assert app.exec_log.scroll_y >= 20
            app.exit()

    asyncio.run(run())


def test_tui_thread_write_log_dispatches_rc_status_message(tmp_path: Path) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            app.thread_write_log(RcStatusMessage((("/Users/me/.zshrc", 0),)))
            await asyncio.sleep(0.2)

            title = app.query_one("#exec-title", Static).render().plain
            assert "shell:" in title
            assert ".zshrc" in title
            assert "shell:" not in str(app.exec_log.lines)
            app.exit()

    asyncio.run(run())


def test_tui_title_shows_shell_status_pending_and_loaded(tmp_path: Path, monkeypatch) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        app.start_rc_probe = lambda: None  # type: ignore[method-assign]
        monkeypatch.setenv("SHELL", "/bin/zsh")
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)

            title = app.query_one("#exec-title", Static)
            assert "shell: zsh  rc: pending" in title.render().plain

            app.write_rc_status((("/Users/me/.zshenv", 0), ("/Users/me/.zshrc", 1)))

            status = title.render().plain
            assert "shell: zsh" in status
            assert "loaded (.zshenv)" in status
            assert "failed (.zshrc) ignored" in status
            app.exit()

    asyncio.run(run())


def test_tui_rc_status_updates_title_without_log_noise(tmp_path: Path, monkeypatch) -> None:
    async def run() -> None:
        app = await _make_app(tmp_path)
        app.start_rc_probe = lambda: None  # type: ignore[method-assign]
        monkeypatch.setenv("SHELL", "/bin/zsh")
        async with app.run_test(size=(120, 32)):
            await asyncio.sleep(0.5)
            app.write_rc_status((("/Users/me/.zshenv", 0), ("/Users/me/.zshrc", 1)))
            app.write_rc_status((("/Users/me/.zshenv", 0),))

            text = app.query_one("#exec-title", Static).render().plain
            assert "shell:" in text
            assert "zsh" in text
            assert "loaded" in text
            assert ".zshenv" in text
            assert text.count("shell:") == 1
            assert "shell:" not in str(app.exec_log.lines)
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
