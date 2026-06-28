from __future__ import annotations

import subprocess
from pathlib import Path


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), text=True, check=True, stdout=subprocess.PIPE)


def init_repo(path: Path, branch: str = "main") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-b", branch], path)
    run(["git", "config", "user.email", "test@example.com"], path)
    run(["git", "config", "user.name", "Test User"], path)
    (path / "README.md").write_text("test\n", encoding="utf-8")
    run(["git", "add", "README.md"], path)
    run(["git", "commit", "-m", "init"], path)
    return path

