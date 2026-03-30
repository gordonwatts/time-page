"""Validate command implementation."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from committee_builder.io.paths import normalize_yaml_path
from committee_builder.pipeline.validate_pipeline import validate_yaml

logger = logging.getLogger(__name__)


def validate_command(
    input_yaml: Path = typer.Argument(
        ...,
        dir_okay=False,
        help="Path to the YAML file to validate (.yaml added if omitted).",
    )
) -> None:
    """Validate YAML schema and semantic correctness."""
    input_yaml = normalize_yaml_path(input_yaml)
    if not input_yaml.is_file():
        raise typer.BadParameter(f"Project file not found: {input_yaml}")
    try:
        result = validate_yaml(input_yaml)
    except Exception as exc:  # noqa: BLE001
        logger.error("Validation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    for warning in result.warnings:
        logger.warning("%s", warning)

    logger.info(
        "Validation successful for %s (%d event(s))",
        input_yaml,
        len(result.history.events),
    )
