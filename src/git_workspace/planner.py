from __future__ import annotations

from .git import repo_state
from .models import PlanItem, Repo, Workspace


def target_branch(workspace: Workspace, repo: Repo, profile: str | None = None) -> str:
    if profile:
        mapping = workspace.config.profiles.get(profile, {})
        if repo.name in mapping:
            return mapping[repo.name]
        if "*" in mapping:
            return mapping["*"]
    return repo.default_branch or "main"


def build_plan(workspace: Workspace, profile: str | None = None) -> list[PlanItem]:
    items: list[PlanItem] = []
    for repo in workspace.repos:
        state = repo_state(repo)
        target = target_branch(workspace, repo, profile)
        if state.branch == target and state.dirty:
            action = "skip pull"
            note = "dirty worktree"
        elif state.branch == target:
            action = "pull"
            note = "already on target"
        elif state.dirty:
            action = "blocked"
            note = "dirty worktree; checkout skipped"
        else:
            action = "checkout + pull"
            note = ""
        items.append(
            PlanItem(
                repo=repo,
                current=state.branch,
                target=target,
                dirty=state.dirty,
                action=action,
                note=note,
            )
        )
    return items

