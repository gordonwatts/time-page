"""Shared date range parsing and resolution helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import typer

from committee_builder.pipeline.validate_pipeline import validate_yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedRangeOptions:
    """Parsed date range options from CLI arguments."""

    from_date: date | None
    to_date: date | None
    past_weeks: int | None
    future_weeks: int | None


def parse_iso_date_option(value: str | None, *, option_name: str) -> date | None:
    """Parse a single ISO date option."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(
            f"{option_name} must be in YYYY-MM-DD format."
        ) from exc


def parse_cli_range_options(
    *,
    from_date: str | None,
    to_date: str | None,
    past_weeks: int | None,
    future_weeks: int | None,
) -> ParsedRangeOptions:
    """Parse CLI date range options into a typed container."""
    return ParsedRangeOptions(
        from_date=parse_iso_date_option(from_date, option_name="--from"),
        to_date=parse_iso_date_option(to_date, option_name="--to"),
        past_weeks=past_weeks,
        future_weeks=future_weeks,
    )


def resolve_cli_range(
    options: ParsedRangeOptions,
    *,
    require_absolute_pair: bool = True,
    default_relative_weeks: tuple[int, int] | None = None,
    today: date | None = None,
) -> tuple[date, date] | None:
    """Resolve absolute/relative CLI options into an inclusive date range."""
    has_absolute = options.from_date is not None or options.to_date is not None
    has_relative = options.past_weeks is not None or options.future_weeks is not None

    if has_absolute and has_relative:
        raise typer.BadParameter(
            "Use either --from/--to or --past-weeks/--future-weeks, not both."
        )

    if has_absolute:
        if require_absolute_pair and (
            options.from_date is None or options.to_date is None
        ):
            raise typer.BadParameter(
                "Both --from and --to are required for absolute ranges."
            )
        if options.from_date is None or options.to_date is None:
            return None
        if options.to_date < options.from_date:
            raise typer.BadParameter("--to cannot be before --from.")
        return options.from_date, options.to_date

    if has_relative or default_relative_weeks is not None:
        current_day = today or date.today()
        default_past, default_future = default_relative_weeks or (0, 0)
        effective_past_weeks = (
            options.past_weeks if options.past_weeks is not None else default_past
        )
        effective_future_weeks = (
            options.future_weeks if options.future_weeks is not None else default_future
        )
        start = current_day - timedelta(weeks=effective_past_weeks)
        end = current_day + timedelta(weeks=effective_future_weeks)
        if end < start:
            raise typer.BadParameter("Computed relative range is invalid.")
        return start, end

    return None


def resolve_build_range(
    *,
    project_yaml: Path,
    options: ParsedRangeOptions,
    today: date | None = None,
) -> tuple[date, date]:
    """Resolve the effective build range with CLI, project, and default precedence."""
    cli_range = resolve_cli_range(options, require_absolute_pair=True)
    if cli_range is not None:
        return cli_range

    project_window = validate_yaml(project_yaml).history.date_window
    if project_window.end_date is not None:
        return project_window.start_date, project_window.end_date

    current_day = today or date.today()
    default_start = current_day - timedelta(weeks=1)
    default_end = current_day + timedelta(weeks=1)
    logger.warning(
        "No CLI or project end_date provided; defaulting date range to %s through %s.",
        default_start.isoformat(),
        default_end.isoformat(),
    )
    return default_start, default_end
