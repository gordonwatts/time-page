"""Init command implementation."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from committee_builder.io.yaml_io import write_yaml

logger = logging.getLogger(__name__)


STARTER_DOC = {
    "schema_version": "1.0",
    "metadata": {
        "name": "Committee Name",
        "subtitle": "Optional subtitle",
        "description_md": "Optional markdown description.",
        "notes_md": "Optional committee notes in markdown.",
    },
    "date_window": {
        "start_date": "2023-01-01",
        "end_date": "2024-12-31",
    },
    "event_type_styles": {
        "meeting": {"label": "Meeting", "color": "sky"},
        "report": {"label": "Report", "color": "emerald"},
        "decision": {"label": "Decision", "color": "rose"},
        "milestone": {"label": "Milestone", "color": "amber"},
        "external": {"label": "External", "color": "violet"},
    },
    "events": [
        {
            "id": "evt-001",
            "type": "meeting",
            "title": "Kickoff Meeting",
            "date": "2023-01-12",
            "important": True,
            "short_label": "Kickoff",
            "summary_md": "# Kickoff\n\nCreated scope, cadence, and timeline.",
            "participants": ["A. Smith", "B. Jones"],
            "tags": ["kickoff", "planning"],
            "documents": [{"label": "Agenda"}, {"label": "Minutes"}],
        }
    ],
}


def init_command(
    path: Path = typer.Argument(
        ..., help="Path where the starter YAML should be created."
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing file if present."
    ),
) -> None:
    """Create a starter YAML source file."""
    if path.exists() and not force:
        logger.error("File already exists: %s (use --force to overwrite)", path)
        raise typer.Exit(code=1)

    write_yaml(path, STARTER_DOC)
    logger.info("Starter file created: %s", path)
