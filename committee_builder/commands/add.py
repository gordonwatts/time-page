"""Top-level add command implementations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import typer

from committee_builder.commands.sources import add_source_command
from committee_builder.commands.add_minutes import add_minutes_command
from committee_builder.io.yaml_io import read_yaml, write_yaml

logger = logging.getLogger(__name__)


def add_event_command(
    project_yaml: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Project YAML path."
    ),
    title: str = typer.Option(..., "--title", help="Event title."),
    date: str = typer.Option(..., "--date", help="Event date in YYYY-MM-DD."),
    event_id: str | None = typer.Option(None, "--id", help="Optional event id."),
    event_type: str = typer.Option("meeting", "--type", help="Event type."),
    summary_md: str = typer.Option(
        "Added from committee add event.", "--summary-md", help="Markdown summary."
    ),
) -> None:
    """Add a local event entry directly to a project YAML file."""
    payload = read_yaml(project_yaml)
    events = payload.setdefault("events", [])
    if not isinstance(events, list):
        raise typer.BadParameter("`events` must be a list in the project YAML.")

    new_event_id = event_id or f"evt-{len(events) + 1:03d}"
    event_doc: dict[str, Any] = {
        "id": new_event_id,
        "type": event_type,
        "title": title,
        "date": date,
        "important": False,
        "summary_md": summary_md,
        "participants": [],
        "tags": [],
        "documents": [],
        "contributions": [],
    }
    events.append(event_doc)
    write_yaml(project_yaml, payload)
    logger.info("Added event '%s' to %s", new_event_id, project_yaml)


def add_indico_category_command(
    project_config: Path = typer.Argument(
        ..., help="Project config path or project name (adds .yaml if omitted)."
    ),
    category_url: str = typer.Argument(
        ..., help="Full Indico category URL, e.g. https://host/category/1234/."
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Optional source title. Defaults to fetched category title.",
    ),
) -> None:
    """Add an Indico category source to project configuration."""
    add_source_command(config=project_config, category_url=category_url, title=title)
