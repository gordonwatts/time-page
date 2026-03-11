"""Schema models for committee history source files."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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


class EventTypeStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    color: str = Field(min_length=1)


class CommitteeMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    subtitle: str | None = None
    description_md: str | None = None
    start_date: date
    end_date: date | None = None
    notes_md: str | None = None


class CommitteeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: EventType
    title: str = Field(min_length=1)
    date: date
    important: bool = False
    short_label: str | None = None
    summary_md: str = Field(min_length=1)
    participants: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    documents: list[DocumentRef] = Field(default_factory=list)


class CommitteeHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0")
    committee: CommitteeMetadata
    event_type_styles: dict[EventType, EventTypeStyle]
    events: list[CommitteeEvent] = Field(default_factory=list)
