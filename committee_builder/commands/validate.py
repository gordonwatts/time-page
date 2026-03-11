"""Validate command implementation."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from committee_builder.pipeline.validate_pipeline import validate_yaml

logger = logging.getLogger(__name__)


def validate_command(
    input_yaml: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to the YAML file to validate.",
    )
) -> None:
    """Validate YAML schema and semantic correctness."""
    try:
        result = validate_yaml(input_yaml)
    except Exception as exc:  # noqa: BLE001
        logger.error("Validation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    for warning in result.warnings:
        logger.warning("%s", warning)

    logger.info("Validation successful for %s (%d event(s))", input_yaml, len(result.history.events))
