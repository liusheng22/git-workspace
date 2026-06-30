from __future__ import annotations

from pathlib import Path

import yaml


def test_publish_requires_full_test_matrix() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/publish.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    assert jobs["publish"]["needs"] == "test"
    matrix = jobs["test"]["strategy"]["matrix"]
    assert set(matrix["os"]) == {"ubuntu-latest", "macos-latest"}
    assert set(matrix["python-version"]) == {"3.11", "3.12", "3.13"}
    assert "pypa/gh-action-pypi-publish@release/v1" in [
        step.get("uses") for step in jobs["publish"]["steps"] if isinstance(step, dict)
    ]


def test_ci_and_publish_use_same_test_matrix() -> None:
    ci = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    publish = yaml.safe_load(Path(".github/workflows/publish.yml").read_text(encoding="utf-8"))

    assert ci["jobs"]["test"]["strategy"]["matrix"] == publish["jobs"]["test"]["strategy"]["matrix"]
