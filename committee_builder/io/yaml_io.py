"""YAML IO helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from committee_builder.schema.models import ProjectFile


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML root must be an object/map.")
    return data


def _strip_none_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_none_values(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_strip_none_values(item) for item in value]
    return value


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(_strip_none_values(data), f, sort_keys=False, allow_unicode=True)


def load_project_file(path: Path) -> ProjectFile:
    """Load a project YAML file from disk."""
    raw = read_yaml(path)
    return ProjectFile.model_validate(raw)


def save_project_file(path: Path, project: ProjectFile) -> None:
    """Persist a project YAML file to disk."""
    write_yaml(path, project.model_dump(mode="json"))
