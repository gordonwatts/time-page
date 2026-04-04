"""Schema models for committee project source files."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from committee_builder.date_parsing import parse_date_expression


class EventType(str, Enum):
    meeting = "meeting"
    report = "report"
    decision = "decision"
    milestone = "milestone"
    external = "external"


class DocumentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    url: str | None = None
    talk_title: str | None = None
    speaker_names: list[str] = Field(default_factory=list)


class ContributionRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    speaker_names: list[str] = Field(default_factory=list)
    documents: list[DocumentRef] = Field(default_factory=list)
    minutes_md: str | None = None


class EventTypeStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    color: str = Field(min_length=1)


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    subtitle: str | None = None
    description_md: str | None = None
    notes_md: str | None = None


class DateWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _parse_date_expression(cls, value: object) -> object:
        return parse_date_expression(value, label="date_window")


class CommitteeMetadata(ProjectMetadata):
    """Backward-compatible metadata view for older call sites."""

    start_date: date
    end_date: date | None = None


class CommitteeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: EventType
    title: str = Field(min_length=1)
    date: date
    important: bool = False
    short_label: str | None = None
    summary_md: str = Field(min_length=1)
    minutes_md: str | None = None
    participants: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    documents: list[DocumentRef] = Field(default_factory=list)
    contributions: list[ContributionRef] = Field(default_factory=list)
    source_name: str | None = None
    source_color: str | None = None


class CommitteeHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0")
    metadata: ProjectMetadata
    date_window: DateWindow
    event_type_styles: dict[EventType, EventTypeStyle]
    events: list[CommitteeEvent] = Field(default_factory=list)
    indico_meeting_source: IndicoSource | None = None
    indico_category_sources: list[IndicoSource] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)

        committee = data.pop("committee", None)
        if isinstance(committee, dict):
            if "metadata" not in data:
                data["metadata"] = {
                    "name": committee.get("name"),
                    "subtitle": committee.get("subtitle"),
                    "description_md": committee.get("description_md"),
                    "notes_md": committee.get("notes_md"),
                }
            if "date_window" not in data:
                data["date_window"] = {
                    "start_date": committee.get("start_date"),
                    "end_date": committee.get("end_date"),
                }

        if "sources" in data and "indico_category_sources" not in data:
            data["indico_category_sources"] = data.pop("sources")
        if "metadata" not in data:
            data["metadata"] = {"name": "Committee Project"}
        if "date_window" not in data:
            data["date_window"] = {"start_date": date.today().isoformat()}
        if "event_type_styles" not in data:
            data["event_type_styles"] = {}
        if "events" not in data:
            data["events"] = []
        return data

    @property
    def committee(self) -> CommitteeMetadata:
        return CommitteeMetadata(
            name=self.metadata.name,
            subtitle=self.metadata.subtitle,
            description_md=self.metadata.description_md,
            notes_md=self.metadata.notes_md,
            start_date=self.date_window.start_date,
            end_date=self.date_window.end_date,
        )


ProjectFile = CommitteeHistory


class IndicoSource(BaseModel):
    """Configured Indico category source."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    category_id: int
    base_url: str = Field(min_length=1)
    color: str = Field(min_length=1)
    title_matches: list[str] = Field(default_factory=list)
    title_exclude_patterns: list[str] = Field(default_factory=list)
