from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, RichLog, Static, TextArea

from .executor import ResolvedCommand, process_env, resolve_command, terminate_process
from .git import repo_state
from .models import ExecMode, Repo, Workspace
from .styles import branch_style, shorten, status_style
from .terminal import SelectionFriendlyLinuxDriver
from .workspace import load_workspace


@dataclass(frozen=True)
class QueuedCommand:
    repo: Repo
    value: str
    mode: ExecMode


@dataclass(frozen=True)
class CommandTarget:
    scope: str
    repo: Repo | None = None

    @property
    def is_all(self) -> bool:
        return self.scope == "all"


@dataclass(frozen=True)
class BatchCommand:
    value: str
    mode: ExecMode
    repos: tuple[Repo, ...]


@dataclass(frozen=True)
class KeyDebugState:
    raw_hex: str = "-"
    raw_repr: str = "-"
    decoded_repr: str = "-"
    key: str = "-"
    character_repr: str = "-"
    normalized_repr: str = "-"
    dropped: bool = False


class LogMessage(Message):
    def __init__(self, renderable: object) -> None:
        super().__init__()
        self.renderable = renderable


class CommandFinished(Message):
    def __init__(self, repo: Repo, returncode: int, elapsed: float) -> None:
        super().__init__()
        self.repo = repo
        self.returncode = returncode
        self.elapsed = elapsed


class RepoTable(DataTable):
    can_focus = False

    async def _on_key(self, event: events.Key) -> None:
        if event.is_printable and event.character:
            app = self.app
            if hasattr(app, "receive_text_input"):
                event.prevent_default()
                event.stop()
                app.receive_text_input(event.character)
                return
        await super()._on_key(event)

    def action_cursor_up(self) -> None:
        if self.row_count <= 0:
            return
        if self.cursor_row <= 0:
            self.move_cursor(row=self.row_count - 1, scroll=True)
            return
        super().action_cursor_up()

    def action_cursor_down(self) -> None:
        if self.row_count <= 0:
            return
        if self.cursor_row >= self.row_count - 1:
            self.move_cursor(row=0, scroll=True)
            return
        super().action_cursor_down()


class CommandLog(RichLog):
    can_focus = False


class CommandInput(TextArea):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.cursor_blink = False

    async def _on_key(self, event: events.Key) -> None:
        if event.key in {"shift+enter", "shift+\r", "shift+\n"}:
            event.prevent_default()
            event.stop()
            start, end = self.selection
            self._replace_via_keyboard("\n", start, end)
            return
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self, self.text))
            return
        await super()._on_key(event)

    class Submitted(Message):
        def __init__(self, input: CommandInput, value: str) -> None:
            super().__init__()
            self.input = input
            self.value = value


class GitWorkspace(App[None]):
    ENABLE_COMMAND_PALETTE = False
    TITLE = "Git Workspace"

    CSS = """
    Screen {
        background: #0d1117;
        color: #c9d1d9;
    }

    Header, Footer {
        background: #161b22;
        color: #e6edf3;
    }

    Header {
        text-style: bold;
        height: 1;
    }

    Header > .header--title {
        text-style: bold;
        color: #58a6ff;
    }

    Header > .header--key {
        color: #58a6ff;
    }

    HeaderIcon {
        display: none;
        width: 0;
        padding: 0;
    }

    Footer {
        background: #161b22;
        height: 1;
    }

    Footer > .footer--key {
        color: #58a6ff;
        text-style: bold;
    }

    Footer > .footer--description {
        color: #8b949e;
    }

    #layout {
        height: 1fr;
        padding: 0;
    }

    #left {
        width: 42;
        min-width: 36;
        max-width: 48;
        border: none;
        border-right: solid #30363d;
        background: #0d1117;
        padding: 0;
    }

    #right {
        width: 1fr;
        border: none;
        background: #0d1117;
        padding: 0;
    }

    #repo-title, #exec-title {
        height: 1;
        padding: 0 1;
        color: #58a6ff;
        text-style: bold;
        background: #161b22;
    }

    #key-debug {
        display: none;
        height: 4;
        padding: 0 1;
        background: #0d1117;
        color: #e6edf3;
        border-bottom: solid #30363d;
    }

    #key-debug.-enabled {
        display: block;
    }

    #repo-table {
        height: 1fr;
        background: #0d1117;
        color: #c9d1d9;
    }

    #repo-table > .datatable--header {
        background: #21262d;
        color: #58a6ff;
        text-style: bold;
        border-bottom: solid #30363d;
    }

    #repo-table > .datatable--odd-row {
        background: transparent;
    }

    #repo-table > .datatable--even-row {
        background: #161b22 30%;
    }

    #repo-table > .datatable--odd-row:hover {
        background: #21262d 50%;
    }

    #repo-table > .datatable--even-row:hover {
        background: #21262d 50%;
    }

    #repo-table > .datatable--cursor {
        background: #1f6feb;
        color: #ffffff;
        text-style: bold;
    }

    #repo-table > .datatable--cursor-cell {
        background: #1f6feb;
        color: #ffffff;
        text-style: bold;
    }

    #exec-log {
        height: 1fr;
        padding: 0 1;
        background: #0d1117;
        color: #c9d1d9;
    }

    #command-line {
        height: 5;
        margin: 0;
        padding: 0 1;
        border-top: solid #30363d;
        background: #161b22;
    }

    #command-line:focus-within {
        border-top: solid #58a6ff;
        background: #21262d;
    }

    #prompt {
        width: auto;
        min-width: 14;
        max-width: 32;
        height: 3;
        content-align: left top;
        color: #58a6ff;
        text-style: bold;
        padding: 0 1;
    }

    #cmd {
        width: 1fr;
        height: 3;
        padding: 0 1;
        border: none;
        background: transparent;
        color: #e6edf3;
        scrollbar-size: 1 1;
    }

    #cmd:focus {
        background: transparent;
        color: #ffffff;
    }

    #cmd .text-area--cursor {
        color: #58a6ff;
        text-style: bold;
    }

    #cmd .text-area--placeholder {
        color: #6e7681;
    }

    #cmd .text-area--cursor-line {
        background: transparent;
    }

    #exec-log {
        scrollbar-background: #161b22;
        scrollbar-background-hover: #21262d;
        scrollbar-color: #30363d;
        scrollbar-color-hover: #58a6ff;
        scrollbar-size: 1 1;
    }

    #repo-table {
        scrollbar-background: #161b22;
        scrollbar-background-hover: #21262d;
        scrollbar-color: #30363d;
        scrollbar-color-hover: #58a6ff;
        scrollbar-size: 1 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "interrupt", "取消/退出", priority=True),
        Binding("tab", "next_repo", "下个仓库", priority=True),
        Binding("shift+tab", "previous_repo", "上个仓库", priority=True),
        Binding("ctrl+q", "quit", show=False, priority=True),
        ("ctrl+r", "refresh", "刷新"),
        ("ctrl+l", "clear_log", "清屏"),
        Binding("pageup", "log_page_up", "日志上翻", key_display="fn+↑", priority=True),
        Binding("pagedown", "log_page_down", "日志下翻", key_display="fn+↓", priority=True),
        Binding("ctrl+j", "next_repo", show=False, priority=True),
        Binding("ctrl+k", "previous_repo", show=False, priority=True),
        Binding("alt+down", "next_repo", show=False, priority=True),
        Binding("alt+up", "previous_repo", show=False, priority=True),
        Binding("ctrl+o", "focus_input", show=False, priority=True),
        ("ctrl+x", "cancel_command", "取消命令"),
    ]

    def __init__(self, start: Path | None = None) -> None:
        super().__init__(driver_class=SelectionFriendlyLinuxDriver)
        self.start = start
        self.workspace: Workspace = load_workspace(start)
        self.repos: list[Repo] = list(self.workspace.repos)
        self.exec_mode = self.workspace.config.exec_settings.default_mode
        self.history: list[str] = []
        self.history_index: int | None = None
        self.pending: deque[QueuedCommand] = deque()
        self.current_batch: BatchCommand | None = None
        self.current_batch_index = 0
        self.batch_queue: deque[BatchCommand] = deque()
        self.command_running = False
        self.current_process: subprocess.Popen[str] | None = None
        self.cancel_requested = False
        self.key_debug_enabled = os.environ.get("GWS_KEY_DEBUG") == "1"
        self.key_debug_state = KeyDebugState()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="layout"):
            with Vertical(id="left"):
                yield Static("ALL / 仓库  Tab/Shift+Tab", id="repo-title")
                yield RepoTable(
                    show_header=True,
                    show_row_labels=False,
                    zebra_stripes=True,
                    cursor_type="row",
                    cell_padding=0,
                    id="repo-table",
                )
            with Vertical(id="right"):
                yield Static("exec", id="exec-title")
                yield Static("", id="key-debug")
                yield CommandLog(id="exec-log", max_lines=5000, wrap=True, highlight=True, markup=False)
                with Horizontal(id="command-line"):
                    yield Static("shell ›", id="prompt")
                    yield CommandInput(
                        placeholder="输入命令，Enter 执行；Shift+Enter 换行；:git / :shell 切换模式",
                        id="cmd",
                        compact=True,
                        highlight_cursor_line=False,
                    )
        yield Footer()

    def on_mount(self) -> None:
        self.populate_repo_table()
        self.repo_table.move_cursor(row=0, column=0, scroll=True)
        self.update_context()
        if not self.repos:
            self.write_log(Text("当前工作区没有发现 Git 仓库", style="bold #f85149"))
        self.update_key_debug()
        self.focus_command_input()
        self.call_after_refresh(self.focus_command_input)

    @property
    def repo_table(self) -> RepoTable:
        return self.query_one("#repo-table", RepoTable)

    @property
    def exec_log(self) -> RichLog:
        return self.query_one("#exec-log", RichLog)

    @property
    def command_input(self) -> CommandInput:
        return self.query_one("#cmd", CommandInput)

    @property
    def prompt(self) -> Static:
        return self.query_one("#prompt", Static)

    @property
    def key_debug(self) -> Static:
        return self.query_one("#key-debug", Static)

    @property
    def selected_repo(self) -> Repo | None:
        if not self.repos or self.repo_table.cursor_row <= 0:
            return None
        row = max(0, min(self.repo_table.cursor_row - 1, len(self.repos) - 1))
        return self.repos[row]

    @property
    def selected_target(self) -> CommandTarget:
        if self.repo_table.cursor_row <= 0:
            return CommandTarget("all")
        repo = self.selected_repo
        if repo is None:
            return CommandTarget("all")
        return CommandTarget("repo", repo)

    def focus_command_input(self) -> None:
        self.set_focus(self.command_input)
        self.command_input.focus()

    def receive_text_input(self, text: str) -> None:
        self.focus_command_input()
        self.command_input.insert(text, maintain_selection_offset=False)

    def set_command_text(self, value: str) -> None:
        self.command_input.load_text(value)
        self.command_input.move_cursor(self.command_input.document.end)

    def clear_command_input(self) -> None:
        self.command_input.load_text("")

    def update_key_debug(self) -> None:
        debug = self.key_debug
        debug.set_class(self.key_debug_enabled, "-enabled")
        if not self.key_debug_enabled:
            debug.update("")
            return
        state = self.key_debug_state
        dropped = "yes" if state.dropped else "no"
        debug.update(
            Text.assemble(
                ("KEY DEBUG  ", "bold #d29922"),
                ("raw ", "bold #58a6ff"),
                (state.raw_hex, "#e6edf3"),
                "\n",
                ("repr ", "bold #58a6ff"),
                (state.raw_repr, "#c9d1d9"),
                ("  decoded ", "bold #58a6ff"),
                (state.decoded_repr, "#c9d1d9"),
                "\n",
                ("key ", "bold #58a6ff"),
                (state.key, "#e6edf3"),
                ("  char ", "bold #58a6ff"),
                (state.character_repr, "#c9d1d9"),
                ("  normalized ", "bold #58a6ff"),
                (state.normalized_repr, "#c9d1d9"),
                ("  dropped ", "bold #58a6ff"),
                (dropped, "#f85149" if state.dropped else "#3fb950"),
            )
        )

    def record_raw_input(self, raw_data: bytes, decoded_data: str) -> None:
        self.key_debug_state = KeyDebugState(
            raw_hex=" ".join(f"{byte:02x}" for byte in raw_data),
            raw_repr=repr(raw_data),
            decoded_repr=repr(decoded_data),
            key=self.key_debug_state.key,
            character_repr=self.key_debug_state.character_repr,
            normalized_repr=self.key_debug_state.normalized_repr,
            dropped=self.key_debug_state.dropped,
        )
        self.update_key_debug()

    def record_key_event(
        self,
        key: str,
        character: str | None,
        normalized_character: str | None,
        dropped: bool,
    ) -> None:
        self.key_debug_state = KeyDebugState(
            raw_hex=self.key_debug_state.raw_hex,
            raw_repr=self.key_debug_state.raw_repr,
            decoded_repr=self.key_debug_state.decoded_repr,
            key=key,
            character_repr=repr(character),
            normalized_repr=repr(normalized_character),
            dropped=dropped,
        )
        self.update_key_debug()

    def sync_badge(self, ahead: int | None, behind: int | None) -> str:
        parts: list[str] = []
        if ahead:
            parts.append(f"↑{ahead}")
        if behind:
            parts.append(f"↓{behind}")
        return "".join(parts)

    def append_sync_badge(self, text: Text, ahead: int | None, behind: int | None) -> None:
        if ahead:
            text.append(f"  ↑{ahead}", style=status_style("ahead"))
        if behind:
            text.append(f"  ↓{behind}", style=status_style("behind"))

    def repo_cells(self, repo: Repo) -> tuple[Text, Text, Text]:
        state = repo_state(repo)
        name = Text(repo.name, style="bold #e6edf3")

        badge = self.sync_badge(state.ahead, state.behind)
        branch_width = 14
        if badge:
            branch_width = max(5, branch_width - len(badge) - 1)
        branch_text = shorten(state.branch, branch_width)
        if badge:
            branch_text = f"{branch_text} {badge}"
        current_branch = Text(branch_text, style=branch_style(state.branch))

        worktree_status = "dirty" if state.dirty else "clean"
        worktree = Text(worktree_status, style=status_style(worktree_status))

        return name, current_branch, worktree

    def populate_repo_table(self) -> None:
        table = self.repo_table
        table.clear(columns=True)
        table.add_column("repo", width=18, key="repo")
        table.add_column("branch", width=14, key="branch")
        table.add_column("state", width=7, key="state")
        table.add_row(
            Text("ALL REPOS", style="bold #58a6ff"),
            Text("—", style="#6e7681"),
            Text("ALL", style="bold #58a6ff"),
            key="__all__",
        )
        for repo in self.repos:
            table.add_row(*self.repo_cells(repo), key=repo.key)

    def write_log(self, renderable: object) -> None:
        self.exec_log.write(renderable)

    def thread_write_log(self, renderable: object) -> None:
        self.post_message(LogMessage(renderable))

    def on_log_message(self, message: LogMessage) -> None:
        self.write_log(message.renderable)

    def on_command_finished(self, message: CommandFinished) -> None:
        self.finish_command(message.repo, message.returncode, message.elapsed)

    def update_context(self) -> None:
        target = self.selected_target
        if target.is_all:
            title = Text()
            title.append("ALL", style="bold #58a6ff")
            title.append(f"  {len(self.repos)} repos", style="bold #8b949e")
            if self.command_running:
                title.append("  running", style="bold #d29922")
            elif self.batch_queue or self.pending or self.current_batch is not None:
                queued = len(self.pending) + len(self.batch_queue)
                title.append(f"  queued:{queued}", style="bold #d29922")
            self.query_one("#exec-title", Static).update(title)

            prompt = Text()
            prompt.append("ALL", style="bold #58a6ff")
            prompt.append(f" {self.exec_mode.value} ›", style="bold #3fb950")
            self.prompt.update(prompt)
            return

        repo = target.repo
        assert repo is not None

        state = repo_state(repo)
        title = Text()
        title.append(self.exec_mode.value.upper(), style="bold #3fb950")
        title.append(" ")
        title.append(repo.name, style="bold #e6edf3")
        title.append("  branch ", style="#6e7681")
        title.append(state.branch, style=branch_style(state.branch))
        self.append_sync_badge(title, state.ahead, state.behind)
        title.append(f"  {state.dirty_label}", style="bold #f85149" if state.dirty else "bold #3fb950")
        if self.command_running:
            title.append("  running", style="bold #d29922")
        elif self.pending:
            title.append(f"  queued:{len(self.pending)}", style="bold #d29922")
        self.query_one("#exec-title", Static).update(title)

        prompt = Text()
        prompt.append(shorten(repo.name, 10), style="bold #58a6ff")
        prompt.append("@")
        prompt.append(shorten(state.branch, 8), style=branch_style(state.branch))
        prompt.append(f" {self.exec_mode.value} ›", style="bold #3fb950")
        self.prompt.update(prompt)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table is self.repo_table:
            self.update_context()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table is self.repo_table:
            self.focus_command_input()

    def on_key(self, event: events.Key) -> None:
        focused = self.focused
        if event.key == "escape":
            event.prevent_default()
            event.stop()
            self.focus_command_input()
            return

        if focused is self.command_input:
            if event.key == "up":
                event.prevent_default()
                event.stop()
                if self.command_input.cursor_location[0] > 0:
                    self.command_input.action_cursor_up()
                    return
                self.history_previous()
                return
            if event.key == "down":
                event.prevent_default()
                event.stop()
                if self.command_input.cursor_location[0] < self.command_input.document.line_count - 1:
                    self.command_input.action_cursor_down()
                    return
                self.history_next()
                return

        if event.is_printable and event.character and focused is not self.command_input:
            event.prevent_default()
            event.stop()
            self.receive_text_input(event.character)

    def history_previous(self) -> None:
        if not self.history:
            return
        if self.history_index is None:
            self.history_index = len(self.history) - 1
        else:
            self.history_index = max(0, self.history_index - 1)
        self.set_command_text(self.history[self.history_index])

    def history_next(self) -> None:
        if self.history_index is None:
            return
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = None
            self.clear_command_input()
        else:
            self.set_command_text(self.history[self.history_index])

    def on_command_input_submitted(self, event: CommandInput.Submitted) -> None:
        value = event.value.strip()
        self.clear_command_input()
        self.history_index = None
        if not value:
            return
        if self.exec_mode == ExecMode.SHELL:
            self.submit_command(value)
            return
        for command in [part.strip() for part in value.splitlines() if part.strip()]:
            self.submit_command(command)

    def submit_command(self, value: str) -> None:
        if not value:
            return
        if self.handle_builtin_command(value):
            return
        if not self.history or self.history[-1] != value:
            self.history.append(value)
            self.history = self.history[-300:]

        if self.command_running:
            target = self.selected_target
            if target.is_all:
                self.queue_workspace_command(value, self.exec_mode)
                self.update_context()
                return
            repo = target.repo
            if repo is None:
                return
            self.pending.append(QueuedCommand(repo, value, self.exec_mode))
            self.write_log(Text(f"queued: {repo.name} {self.exec_mode.value} › {value}", style="#d29922"))
            self.update_context()
            return
        target = self.selected_target
        if target.is_all:
            self.start_workspace_command(value, self.exec_mode)
            return
        repo = target.repo
        if repo is None:
            return
        self.start_command(repo, value, self.exec_mode)

    def handle_builtin_command(self, value: str) -> bool:
        if value in {":quit", ":q", "quit", "exit"}:
            self.action_quit()
            return True
        if value in {":clear", "clear"}:
            self.action_clear_log()
            return True
        if value in {":refresh", "refresh"}:
            self.action_refresh()
            return True
        if value == ":shell":
            self.exec_mode = ExecMode.SHELL
            self.write_log(Text("mode: shell", style="bold #3fb950"))
            self.update_context()
            self.focus_command_input()
            return True
        if value == ":git":
            self.exec_mode = ExecMode.GIT
            self.write_log(Text("mode: git", style="bold #3fb950"))
            self.update_context()
            self.focus_command_input()
            return True
        if value == ":keys":
            self.key_debug_enabled = not self.key_debug_enabled
            state = "on" if self.key_debug_enabled else "off"
            self.write_log(Text(f"key debug: {state}", style="bold #d29922"))
            self.update_key_debug()
            self.focus_command_input()
            return True
        return False

    def start_command(self, repo: Repo, value: str, mode: ExecMode) -> None:
        try:
            resolved = resolve_command(value, repo, self.workspace.config, mode)
        except ValueError as exc:
            self.write_log(Text(str(exc), style="bold red"))
            return
        if resolved is None:
            return

        state = repo_state(repo)
        context = Text("\n")
        context.append(repo.name, style="bold #58a6ff")
        context.append(" @ ", style="#6e7681")
        context.append(state.branch, style=branch_style(state.branch))
        self.write_log(context)

        line = Text(f"{mode.value} › ", style="bold #3fb950")
        line.append(value, style="bold #e6edf3")
        self.write_log(line)
        if resolved.expanded and resolved.expanded != value:
            self.write_log(Text(f"expanded: {resolved.expanded}", style="#6e7681"))

        self.command_running = True
        self.cancel_requested = False
        self.current_process = None
        self.update_context()
        worker = threading.Thread(target=self.run_command_thread, args=(repo, resolved), daemon=True)
        worker.start()

    def candidate_repos_for_workspace_command(self, value: str) -> list[Repo]:
        command = value.strip()
        if not command:
            return []
        if command.startswith("!"):
            return list(self.repos)
        lowered = command.split(maxsplit=1)[0].lower()
        if lowered in {"git", "g", "gs", "gst", "gco", "gcb", "gsw", "gl", "gp"}:
            return list(self.repos)
        if lowered in {"status", "pull", "push", "fetch", "checkout", "switch", "branch"}:
            return list(self.repos)
        return list(self.repos)

    def start_workspace_command(self, value: str, mode: ExecMode) -> None:
        repos = self.candidate_repos_for_workspace_command(value)
        if not repos:
            self.write_log(Text("当前工作区没有发现 Git 仓库", style="bold #f85149"))
            return
        batch = BatchCommand(value, mode, tuple(repos))
        if self.command_running or self.current_batch is not None:
            self.batch_queue.append(batch)
            self.write_log(Text(f"queued: ALL {mode.value} › {value}", style="#d29922"))
            self.update_context()
            return
        self.current_batch = batch
        self.current_batch_index = 0
        self.write_log(Text(f"scope: ALL ({len(repos)} repos)", style="bold #58a6ff"))
        self.update_context()
        self.start_command(batch.repos[0], batch.value, batch.mode)

    def queue_workspace_command(self, value: str, mode: ExecMode) -> None:
        repos = self.candidate_repos_for_workspace_command(value)
        if not repos:
            return
        self.batch_queue.append(BatchCommand(value, mode, tuple(repos)))
        self.write_log(Text(f"queued: ALL {mode.value} › {value}", style="#d29922"))

    def run_command_thread(self, repo: Repo, resolved: ResolvedCommand) -> None:
        started = time.monotonic()
        returncode = 1
        try:
            proc = subprocess.Popen(
                resolved.args,
                cwd=str(resolved.cwd),
                env=process_env(),
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                start_new_session=True,
            )
            self.current_process = proc
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                if line:
                    self.thread_write_log(line.replace("\r", "\n"))
            returncode = proc.wait()
        except FileNotFoundError as exc:
            self.thread_write_log(Text(f"命令不存在：{exc}", style="bold #f85149"))
            returncode = 127
        except Exception as exc:
            self.thread_write_log(Text(f"执行异常：{exc}", style="bold #f85149"))
            returncode = 1
        finally:
            elapsed = time.monotonic() - started
            self.post_message(CommandFinished(repo, returncode, elapsed))

    def finish_command(self, repo: Repo, returncode: int, elapsed: float) -> None:
        canceled = self.cancel_requested or returncode in {-signal.SIGTERM, -signal.SIGKILL}
        self.command_running = False
        self.current_process = None
        self.cancel_requested = False
        if canceled:
            self.write_log(Text(f"已取消  ({elapsed:.1f}s)", style="bold #d29922"))
        elif returncode == 0:
            self.write_log(Text(f"完成  ({elapsed:.1f}s)", style="bold #3fb950"))
        else:
            self.write_log(Text(f"失败：exit {returncode}  ({elapsed:.1f}s)", style="bold #f85149"))
        self.refresh_repo(repo)
        self.update_context()
        self.focus_command_input()
        self.run_next_queued()

    def run_next_queued(self) -> None:
        if self.command_running:
            return
        if self.pending:
            item = self.pending.popleft()
            self.update_context()
            self.start_command(item.repo, item.value, item.mode)
            return
        if self.current_batch is not None:
            batch = self.current_batch
            if self.current_batch_index + 1 < len(batch.repos):
                self.current_batch_index += 1
                self.update_context()
                self.start_command(
                    batch.repos[self.current_batch_index],
                    batch.value,
                    batch.mode,
                )
                return
            self.write_log(Text(f"ALL completed  ({len(batch.repos)} repos)", style="bold #3fb950"))
            self.current_batch = None
            self.current_batch_index = 0
            self.update_context()
        if self.batch_queue:
            batch = self.batch_queue.popleft()
            self.current_batch = batch
            self.current_batch_index = 0
            self.write_log(Text(f"scope: ALL ({len(batch.repos)} repos)", style="bold #58a6ff"))
            self.update_context()
            self.start_command(batch.repos[0], batch.value, batch.mode)

    def refresh_repo(self, repo: Repo) -> None:
        if repo not in self.repos:
            return
        try:
            name, current_branch, worktree = self.repo_cells(repo)
            row_key = repo.key
            self.repo_table.update_cell(row_key, "repo", name)
            self.repo_table.update_cell(row_key, "branch", current_branch)
            self.repo_table.update_cell(row_key, "state", worktree)
        except Exception:
            pass

    def action_refresh(self) -> None:
        current = self.selected_repo
        self.workspace = load_workspace(self.start)
        self.repos = list(self.workspace.repos)
        self.populate_repo_table()
        if current is not None:
            for index, repo in enumerate(self.repos):
                if repo.path == current.path:
                    self.repo_table.move_cursor(row=index + 1, column=0, scroll=True)
                    break
        else:
            self.repo_table.move_cursor(row=0, column=0, scroll=True)
        self.update_context()
        self.write_log(Text("已刷新仓库列表", style="bold #3fb950"))
        self.focus_command_input()

    def action_clear_log(self) -> None:
        self.exec_log.clear()
        self.focus_command_input()

    def action_log_page_up(self) -> None:
        self.exec_log.scroll_page_up(animate=False)
        self.focus_command_input()

    def action_log_page_down(self) -> None:
        self.exec_log.scroll_page_down(animate=False)
        self.focus_command_input()

    def action_focus_input(self) -> None:
        self.focus_command_input()

    def select_repo_delta(self, delta: int) -> None:
        total_rows = len(self.repos) + 1
        if total_rows <= 0:
            return
        next_row = (self.repo_table.cursor_row + delta) % total_rows
        self.repo_table.move_cursor(row=next_row, column=0, scroll=True)
        self.update_context()
        self.focus_command_input()

    def action_next_repo(self) -> None:
        self.select_repo_delta(1)

    def action_previous_repo(self) -> None:
        self.select_repo_delta(-1)

    def action_cancel_command(self) -> None:
        self.cancel_current_command(show_idle=True)

    def cancel_current_command(self, show_idle: bool = False) -> bool:
        proc = self.current_process
        if not self.command_running or proc is None or proc.poll() is not None:
            if show_idle:
                self.write_log(Text("没有正在执行的命令", style="#6e7681"))
            return False
        self.cancel_requested = True
        self.pending.clear()
        self.current_batch = None
        self.current_batch_index = 0
        self.batch_queue.clear()
        terminate_process(proc)
        self.write_log(Text("正在取消当前命令...", style="#d29922"))
        return True

    def action_interrupt(self) -> None:
        if self.cancel_current_command(show_idle=False):
            return
        self.action_quit()

    def action_help_quit(self) -> None:
        self.action_interrupt()

    def action_quit(self) -> None:
        proc = self.current_process
        if proc is not None and proc.poll() is None:
            self.cancel_requested = True
            terminate_process(proc)
        self.exit()
