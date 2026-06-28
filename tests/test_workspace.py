from __future__ import annotations

from pathlib import Path

from conftest import init_repo

from git_workspace.workspace import load_workspace


def test_discovers_direct_child_repos(tmp_path: Path) -> None:
    init_repo(tmp_path / "api")
    init_repo(tmp_path / "web")
    (tmp_path / "not-repo").mkdir()

    workspace = load_workspace(tmp_path)

    assert [repo.name for repo in workspace.repos] == ["api", "web"]


def test_uses_explicit_repo_config(tmp_path: Path) -> None:
    init_repo(tmp_path / "services" / "api")
    (tmp_path / "workspace.yml").write_text(
        """
repos:
  api:
    path: ./services/api
    default: dev
""",
        encoding="utf-8",
    )

    workspace = load_workspace(tmp_path)

    assert len(workspace.repos) == 1
    assert workspace.repos[0].name == "api"
    assert workspace.repos[0].default_branch == "dev"
