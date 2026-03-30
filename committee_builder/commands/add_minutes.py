"""CLI support for embedding minutes markdown into project events."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import typer

from committee_builder.io.paths import normalize_yaml_path
from committee_builder.io.yaml_io import read_yaml, write_yaml

logger = logging.getLogger(__name__)


def _event_matches_selector(
    event: dict[str, Any], event_selector: str, title: str | None, date: str | None
) -> bool:
    """Return true when an event matches the provided selector options."""
    if title is None:
        return event.get("id") == event_selector

    if date is None:
        return event.get("title") == title

    return event.get("title") == title and event.get("date") == date


def _collect_matching_events(
    events: list[Any], event_selector: str, title: str | None, date: str | None
) -> list[dict[str, Any]]:
    """Collect all event dicts that match selector criteria."""
    matches: list[dict[str, Any]] = []
    for event in events:
        if isinstance(event, dict) and _event_matches_selector(
            event=event,
            event_selector=event_selector,
            title=title,
            date=date,
        ):
            matches.append(event)
    return matches


def add_minutes_command(
    project_yaml: Path = typer.Argument(
        ..., dir_okay=False, help="Project YAML path or project name (adds .yaml if omitted)."
    ),
    event_selector: str = typer.Argument(
        ...,
        help=(
            "Event selector. Defaults to matching by event id unless "
            "--title/--date selector mode is used."
        ),
    ),
    minutes_file: Path = typer.Argument(
        ..., dir_okay=False, readable=True, help="Minutes text/markdown path."
    ),
    field: str = typer.Option(
        "minutes_md",
        "--field",
        help="Event markdown field to fill (minutes_md or summary_md).",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Match by title (optionally combine with --date for specificity).",
    ),
    date: str | None = typer.Option(
        None,
        "--date",
        help="When used with --title, require a specific event date (YYYY-MM-DD).",
    ),
) -> None:
    """Import minutes markdown into an event markdown field."""
    project_yaml = normalize_yaml_path(project_yaml)
    if not project_yaml.is_file():
        raise typer.BadParameter(f"Project file not found: {project_yaml}")
    if field not in {"minutes_md", "summary_md"}:
        raise typer.BadParameter("--field must be minutes_md or summary_md.")
    if date is not None and title is None:
        raise typer.BadParameter("--date can only be used together with --title.")

    try:
        minutes_text = minutes_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"Minutes file not found: {minutes_file}") from exc

    payload = read_yaml(project_yaml)
    events = payload.get("events", [])
    if not isinstance(events, list):
        raise typer.BadParameter("`events` must be a list in the project YAML.")

    matches = _collect_matching_events(
        events=events,
        event_selector=event_selector,
        title=title,
        date=date,
    )

    if not matches:
        if title is None:
            raise typer.BadParameter(f"No event found for id '{event_selector}'.")
        if date is None:
            raise typer.BadParameter(
                f"No event found for title '{title}'. "
                "Pass --date when multiple events share a title."
            )
        raise typer.BadParameter(
            f"No event found for title/date selector '{title}' on {date}."
        )

    if len(matches) > 1:
        if title is None:
            raise typer.BadParameter(
                f"Selector '{event_selector}' matched multiple events unexpectedly."
            )
        raise typer.BadParameter(
            f"Title selector '{title}' is ambiguous; add --date to disambiguate."
        )

    matches[0][field] = minutes_text
    write_yaml(project_yaml, payload)
    logger.info(
        "Imported %s into event '%s' (%s) in %s",
        minutes_file,
        matches[0].get("id", "<unknown>"),
        field,
        project_yaml,
    )
