"""Build command implementation."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from committee_builder.pipeline.build_pipeline import build_html

logger = logging.getLogger(__name__)


def build_command(
    input_yaml: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to the input YAML file.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional output HTML path. Defaults to input path with .html extension.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Allow overwriting an existing output file.",
    ),
) -> None:
    """Build a standalone committee history HTML page.

    The output contains inlined CSS, JS, and committee data.
    """
    try:
        output_path = build_html(input_yaml=input_yaml, output_path=output, overwrite=overwrite)
    except Exception as exc:  # noqa: BLE001
        logger.error("Build failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.info("Build succeeded: %s", output_path)
