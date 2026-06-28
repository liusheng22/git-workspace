from __future__ import annotations

from pathlib import Path

from conftest import init_repo

from git_workspace.planner import build_plan
from git_workspace.workspace import load_workspace


def test_plan_marks_dirty_branch_switch_as_blocked(tmp_path: Path) -> None:
    init_repo(tmp_path / "api", branch="main")
    (tmp_path / "api" / "README.md").write_text("dirty\n", encoding="utf-8")
    (tmp_path / "workspace.yml").write_text(
        """
repos:
  api:
    path: ./api
    default: dev
""",
        encoding="utf-8",
    )

    item = build_plan(load_workspace(tmp_path))[0]

    assert item.action == "blocked"
    assert item.target == "dev"
