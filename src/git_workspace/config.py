from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import ExecMode, ExecSettings, WorkspaceConfig

CONFIG_NAMES = ("workspace.yml", "workspace.yaml")
LOCAL_CONFIG_NAMES = ("workspace.local.yml", "workspace.local.yaml")


def find_config(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        for name in CONFIG_NAMES:
            candidate = directory / name
            if candidate.exists():
                return candidate
    return None


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a mapping")
    return loaded


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _as_mapping(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _as_string_mapping(value: Any, name: str) -> dict[str, str]:
    mapping = _as_mapping(value, name)
    return {str(key): str(val) for key, val in mapping.items()}


def _normalize_repo_config(value: Any) -> dict[str, dict[str, str]]:
    repos = _as_mapping(value, "repos")
    normalized: dict[str, dict[str, str]] = {}
    for name, raw in repos.items():
        if raw is None:
            normalized[str(name)] = {}
        elif isinstance(raw, str):
            normalized[str(name)] = {"path": raw}
        elif isinstance(raw, dict):
            normalized[str(name)] = {str(key): str(val) for key, val in raw.items()}
        else:
            raise ValueError(f"repos.{name} must be a mapping or string")
    return normalized


def _normalize_profiles(value: Any) -> dict[str, dict[str, str]]:
    profiles = _as_mapping(value, "profiles")
    normalized: dict[str, dict[str, str]] = {}
    for name, raw in profiles.items():
        normalized[str(name)] = _as_string_mapping(raw, f"profiles.{name}")
    return normalized


def _normalize_ignore(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise ValueError("workspace.ignore must be a list")
    return tuple(str(item) for item in value)


def _normalize_exec(value: Any) -> ExecSettings:
    raw = _as_mapping(value, "exec")
    mode = str(raw.get("defaultMode", raw.get("default_mode", "shell"))).lower()
    default_mode = ExecMode.GIT if mode == "git" else ExecMode.SHELL
    shell = _as_mapping(raw.get("shell"), "exec.shell")
    return ExecSettings(
        default_mode=default_mode,
        git_shortcuts=bool(raw.get("gitShortcuts", raw.get("git_shortcuts", True))),
        interactive_shell=bool(shell.get("interactive", True)),
    )


def load_config(start: Path | None = None) -> WorkspaceConfig:
    cwd = (start or Path.cwd()).resolve()
    config_file = find_config(cwd)
    if config_file is None:
        return WorkspaceConfig(root=cwd)

    data = _read_yaml(config_file)
    for local_name in LOCAL_CONFIG_NAMES:
        local_file = config_file.parent / local_name
        if local_file.exists():
            data = _deep_merge(data, _read_yaml(local_file))

    workspace = _as_mapping(data.get("workspace"), "workspace")
    root_value = workspace.get("root", ".")
    root = (config_file.parent / str(root_value)).resolve()

    return WorkspaceConfig(
        root=root,
        config_file=config_file,
        ignore=_normalize_ignore(workspace.get("ignore")),
        repos=_normalize_repo_config(data.get("repos")),
        profiles=_normalize_profiles(data.get("profiles")),
        aliases=_as_string_mapping(data.get("aliases"), "aliases"),
        exec_settings=_normalize_exec(data.get("exec")),
    )

