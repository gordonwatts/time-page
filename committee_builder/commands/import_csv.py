"""Placeholder for future CSV import support."""

from __future__ import annotations

import logging

import typer

logger = logging.getLogger(__name__)


def import_csv_command() -> None:
    """Placeholder for importing committee data from CSV."""
    logger.warning("import-csv is not implemented yet.")
    raise typer.Exit(code=1)
