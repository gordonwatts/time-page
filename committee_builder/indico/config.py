"""Compatibility helpers for Indico configuration stored in project YAML."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from committee_builder.io.yaml_io import load_project_file, save_project_file
from committee_builder.schema.models import IndicoSource, ProjectFile


class IndicoConfig(BaseModel):
    """Backward-compatible config view for legacy call sites/tests."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(default="1")
    sources: list[IndicoSource] = Field(default_factory=list)


def load_indico_config(path: Path) -> IndicoConfig:
    if not path.exists():
        return IndicoConfig()
    project = load_project_file(path)
    return IndicoConfig(sources=project.indico_category_sources)


def save_indico_config(path: Path, config: IndicoConfig) -> None:
    project = load_project_file(path) if path.exists() else None
    if project is None:
        today = date.today().isoformat()
        project = ProjectFile.model_validate(
            {
                "schema_version": "1.0",
                "metadata": {"name": path.stem},
                "date_window": {"start_date": today},
                "event_type_styles": {},
                "events": [],
            }
        )
    save_project_file(
        path,
        project.model_copy(update={"indico_category_sources": config.sources}),
    )


__all__ = ["IndicoConfig", "IndicoSource", "load_indico_config", "save_indico_config"]
