"""Build command implementation."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from committee_builder.pipeline.build_pipeline import build_html
from committee_builder.pipeline.date_range import (
    parse_cli_range_options,
    resolve_build_range,
)

logger = logging.getLogger(__name__)


def build_command(
    project_yaml: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to the project YAML file.",
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
    from_date: str | None = typer.Option(
        None, "--from", help="Override start date (YYYY-MM-DD)."
    ),
    to_date: str | None = typer.Option(
        None, "--to", help="Override end date (YYYY-MM-DD)."
    ),
    past_weeks: int | None = typer.Option(
        None, "--past-weeks", help="Bracket range start relative to today."
    ),
    future_weeks: int | None = typer.Option(
        None, "--future-weeks", help="Bracket range end relative to today."
    ),
) -> None:
    """Build a standalone committee history HTML page.

    The output contains inlined CSS, JS, and committee data.
    """
    range_options = parse_cli_range_options(
        from_date=from_date,
        to_date=to_date,
        past_weeks=past_weeks,
        future_weeks=future_weeks,
    )
    range_start, range_end = resolve_build_range(
        project_yaml=project_yaml,
        options=range_options,
    )
    try:
        output_path = build_html(
            input_yaml=project_yaml,
            output_path=output,
            overwrite=overwrite,
            from_date=range_start,
            to_date=range_end,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Build failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.info("Build succeeded: %s", output_path)
