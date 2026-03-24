"""Build command implementation."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import typer

from committee_builder.pipeline.build_pipeline import build_html

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
    parsed_from = _parse_iso_date(from_date, option_name="--from")
    parsed_to = _parse_iso_date(to_date, option_name="--to")
    range_start, range_end = _resolve_range(
        from_date=parsed_from,
        to_date=parsed_to,
        past_weeks=past_weeks,
        future_weeks=future_weeks,
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


def _parse_iso_date(value: str | None, *, option_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(
            f"{option_name} must be in YYYY-MM-DD format."
        ) from exc


def _resolve_range(
    from_date: date | None,
    to_date: date | None,
    past_weeks: int | None,
    future_weeks: int | None,
) -> tuple[date | None, date | None]:
    if (past_weeks is not None or future_weeks is not None) and (
        from_date is not None or to_date is not None
    ):
        raise typer.BadParameter(
            "Use either --from/--to or --past-weeks/--future-weeks."
        )

    if from_date is not None or to_date is not None:
        if from_date is not None and to_date is not None and from_date > to_date:
            raise typer.BadParameter("--from must be before or equal to --to.")
        return from_date, to_date

    if past_weeks is None and future_weeks is None:
        return None, None

    today = date.today()
    range_start = (
        today - timedelta(weeks=past_weeks) if past_weeks is not None else None
    )
    range_end = (
        today + timedelta(weeks=future_weeks) if future_weeks is not None else None
    )
    if range_start is not None and range_end is not None and range_start > range_end:
        raise typer.BadParameter("Computed date window is invalid.")
    return range_start, range_end
