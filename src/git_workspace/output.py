from __future__ import annotations

from rich.console import Console
from rich.table import Table

from .git import repo_state
from .models import PlanItem, Workspace
from .planner import build_plan, target_branch


def print_status(workspace: Workspace, profile: str | None = None) -> None:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("repo")
    table.add_column("branch")
    table.add_column("target")
    table.add_column("sync")
    table.add_column("state")
    table.add_column("upstream")
    for repo in workspace.repos:
        state = repo_state(repo)
        table.add_row(
            repo.name,
            state.branch,
            target_branch(workspace, repo, profile),
            state.sync_label,
            state.dirty_label,
            state.upstream or "-",
        )
    Console().print(table)


def print_plan(workspace: Workspace, profile: str | None = None) -> None:
    items = build_plan(workspace, profile)
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("repo")
    table.add_column("current")
    table.add_column("target")
    table.add_column("dirty")
    table.add_column("action")
    table.add_column("note")
    for item in items:
        table.add_row(
            item.repo.name,
            item.current,
            item.target,
            "yes" if item.dirty else "no",
            item.action,
            item.note,
        )
    Console().print(table)


def plan_items_for_action(workspace: Workspace, profile: str | None, actions: set[str]) -> list[PlanItem]:
    return [item for item in build_plan(workspace, profile) if item.action in actions]

