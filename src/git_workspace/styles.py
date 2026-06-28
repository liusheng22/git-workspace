from __future__ import annotations


def branch_style(value: str) -> str:
    if value in {"main", "master"}:
        return "bold cyan"
    if value in {"dev", "develop", "test", "release"}:
        return "bold magenta"
    if value.startswith("detached:"):
        return "bold yellow"
    return "bold purple"


def shorten(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return f"{value[: width - 1]}~"

