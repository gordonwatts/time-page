"""Build command implementation."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from committee_builder.io.paths import normalize_yaml_path
from committee_builder.pipeline.build_pipeline import build_html
from committee_builder.pipeline.date_range import (
    parse_cli_range_options,
    resolve_build_range,
)

logger = logging.getLogger(__name__)


def build_command(
    project_yaml: Path = typer.Argument(
        ...,
        dir_okay=False,
        help="Path to the project YAML file (.yaml added if omitted).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional output HTML path. Defaults to input path with .html extension.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing output file.",
    ),
    from_date: str | None = typer.Option(
        None, "--from", help="Override start date (ISO, now, -3d, +2w, etc.)."
    ),
    to_date: str | None = typer.Option(
        None, "--to", help="Override end date (ISO, now, +2w, -3d, etc.)."
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
    project_yaml = normalize_yaml_path(project_yaml)
    if not project_yaml.is_file():
        raise typer.BadParameter(f"Project file not found: {project_yaml}")
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
