from __future__ import annotations

from pathlib import Path

from conftest import init_repo

from git_workspace import cli


def test_parse_exec_tokens_without_profile() -> None:
    assert cli.parse_exec_tokens(["--", "pnpm", "test"], {"daily"}) == (None, ["pnpm", "test"])
    assert cli.parse_exec_tokens(["pnpm", "test"], {"daily"}) == (None, ["pnpm", "test"])


def test_parse_exec_tokens_with_profile() -> None:
    assert cli.parse_exec_tokens(["daily", "--", "git", "status"], {"daily"}) == (
        "daily",
        ["git", "status"],
    )
    assert cli.parse_exec_tokens(["daily", "git", "status"], {"daily"}) == (
        "daily",
        ["git", "status"],
    )


def test_pull_does_not_pull_wrong_branch(tmp_path: Path, monkeypatch, capsys) -> None:
    api = init_repo(tmp_path / "api", branch="main")
    web = init_repo(tmp_path / "web", branch="dev")
    (tmp_path / "workspace.yml").write_text(
        """
repos:
  api:
    path: ./api
    default: main
  web:
    path: ./web
    default: main
""",
        encoding="utf-8",
    )

    pulled: list[Path] = []

    def fake_run_git(repo_path: Path, *args: str) -> int:
        assert args == ("pull", "--ff-only")
        pulled.append(repo_path)
        return 0

    monkeypatch.setattr(cli, "run_git", fake_run_git)

    exit_code = cli.do_pull(None, tmp_path)

    assert exit_code == 1
    assert pulled == [api]
    assert "skip web: target branch differs" in capsys.readouterr().out
    assert web not in pulled
