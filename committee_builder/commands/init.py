"""Init command implementation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import typer

from committee_builder.io.paths import normalize_yaml_path
from committee_builder.io.yaml_io import write_yaml

logger = logging.getLogger(__name__)


STARTER_DOC = {
    "schema_version": "1.0",
    "metadata": {
        "name": "Committee Project",
    },
    "date_window": {
        "start_date": "2023-01-01",
        "end_date": "2024-12-31",
    },
    "event_type_styles": {},
    "events": [],
}


def _build_starter_doc(
    title: str, from_date: str, to_date: str | None
) -> dict[str, Any]:
    starter_doc: dict[str, Any] = {
        **STARTER_DOC,
        "metadata": {
            **STARTER_DOC["metadata"],
            "name": title,
        },
        "date_window": {
            "start_date": from_date,
            "end_date": to_date or from_date,
        },
    }
    return starter_doc


def init_command(
    path: Path = typer.Argument(
        ..., help="Path where the blank YAML should be created (.yaml added if omitted)."
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing file if present."
    ),
    title: str = typer.Option(
        "Committee Project",
        "--title",
        help="Project title to store in metadata.name.",
    ),
    from_date: str = typer.Option(
        "2023-01-01",
        "--from",
        help="Default date window start (YYYY-MM-DD).",
    ),
    to_date: str | None = typer.Option(
        "2024-12-31",
        "--to",
        help="Default date window end (YYYY-MM-DD).",
    ),
) -> None:
    """Create a blank YAML source file."""
    path = normalize_yaml_path(path)
    if path.exists() and not force:
        logger.error("File already exists: %s (use --force to overwrite)", path)
        raise typer.Exit(code=1)

    write_yaml(
        path, _build_starter_doc(title=title, from_date=from_date, to_date=to_date)
    )
    logger.info("Blank project file created: %s", path)
