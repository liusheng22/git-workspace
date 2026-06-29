from __future__ import annotations


def branch_style(value: str) -> str:
    if value in {"main", "master"}:
        return "bold #58a6ff"
    if value in {"dev", "develop", "development"}:
        return "bold #d2a8ff"
    if value in {"staging", "stage", "test", "testing"}:
        return "bold #ff7b72"
    if value in {"release", "prod", "production"}:
        return "bold #3fb950"
    if value.startswith("detached:"):
        return "bold #d29922"
    if value.startswith("feature/"):
        return "bold #a5d6ff"
    if value.startswith("fix/"):
        return "bold #ffa657"
    if value.startswith("hotfix/"):
        return "bold #f85149"
    return "bold #79c0ff"


def status_style(status: str) -> str:
    status_lower = status.lower()
    if status_lower in {"clean", "✓"}:
        return "bold #3fb950"
    if status_lower in {"dirty", "modified", "✗"}:
        return "bold #f85149"
    if status_lower in {"ahead", "↑"}:
        return "bold #d29922"
    if status_lower in {"behind", "↓"}:
        return "bold #58a6ff"
    if status_lower in {"diverged", "⇄"}:
        return "bold #d2a8ff"
    return "bold #8b949e"


def shorten(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return f"{value[: width - 1]}~"

