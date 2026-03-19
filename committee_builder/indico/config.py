"""Models and persistence helpers for Indico source configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from committee_builder.io.yaml_io import read_yaml, write_yaml


class IndicoSource(BaseModel):
    """Single configured Indico category source."""

    # Ignore legacy per-source credential fields if present in existing files.
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    category_id: int
    base_url: str = Field(min_length=1)
    color: str = Field(min_length=1)
    title_matches: list[str] = Field(default_factory=list)


class IndicoConfig(BaseModel):
    """Root configuration file for Indico source definitions."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(default="1")
    sources: list[IndicoSource] = Field(default_factory=list)


def load_indico_config(path: Path) -> IndicoConfig:
    """Load config from disk, returning an empty config when file is missing."""
    if not path.exists():
        return IndicoConfig()
    raw_data = read_yaml(path)
    return IndicoConfig.model_validate(raw_data)


def save_indico_config(path: Path, config: IndicoConfig) -> None:
    """Persist config to disk in a deterministic order."""
    serialized = config.model_dump(mode="json")
    serialized["sources"] = sorted(serialized["sources"], key=lambda item: item["name"])
    for source in serialized["sources"]:
        if not source.get("title_matches"):
            source.pop("title_matches", None)
    write_yaml(path, serialized)
