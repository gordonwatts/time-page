"""Tests for shared date range resolution."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
import typer

from committee_builder.pipeline import date_range
from committee_builder.date_parsing import parse_date_expression
from committee_builder.pipeline.date_range import (
    ParsedRangeOptions,
    parse_date_option,
    parse_cli_range_options,
    resolve_build_range,
    resolve_cli_range,
)


def _write_project(path: Path, *, start_date: str, end_date: str | None) -> None:
    end_date_yaml = f'"{end_date}"' if end_date is not None else "null"
    path.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "metadata:",
                '  name: "Range Test"',
                "date_window:",
                f'  start_date: "{start_date}"',
                f"  end_date: {end_date_yaml}",
                "event_type_styles:",
                '  meeting: {label: "Meeting", color: "sky"}',
                '  report: {label: "Report", color: "emerald"}',
                '  decision: {label: "Decision", color: "rose"}',
                '  milestone: {label: "Milestone", color: "amber"}',
                '  external: {label: "External", color: "violet"}',
                "events: []",
            ]
        ),
        encoding="utf-8",
    )


def test_resolve_cli_range_rejects_mixed_absolute_and_relative() -> None:
    options = ParsedRangeOptions(
        from_date=date(2025, 1, 1),
        to_date=date(2025, 1, 2),
        past_weeks=1,
        future_weeks=None,
    )

    with pytest.raises(typer.BadParameter, match="Use either --from/--to"):
        resolve_cli_range(options)


def test_resolve_cli_range_rejects_partial_absolute() -> None:
    options = ParsedRangeOptions(
        from_date=date(2025, 1, 1),
        to_date=None,
        past_weeks=None,
        future_weeks=None,
    )

    with pytest.raises(typer.BadParameter, match="Both --from and --to"):
        resolve_cli_range(options, require_absolute_pair=True)


def test_resolve_build_range_prefers_cli_absolute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If CLI options are present, project-file loading should not be needed.
    monkeypatch.setattr(
        date_range,
        "validate_yaml",
        lambda _path: (_ for _ in ()).throw(AssertionError("should not load project")),
    )
    options = ParsedRangeOptions(
        from_date=date(2025, 2, 1),
        to_date=date(2025, 2, 14),
        past_weeks=None,
        future_weeks=None,
    )

    resolved = resolve_build_range(project_yaml=Path("unused.yaml"), options=options)

    assert resolved == (date(2025, 2, 1), date(2025, 2, 14))


def test_resolve_build_range_prefers_cli_relative(tmp_path: Path) -> None:
    project_path = tmp_path / "committee.yaml"
    _write_project(project_path, start_date="2020-01-01", end_date="2020-12-31")
    options = ParsedRangeOptions(
        from_date=None,
        to_date=None,
        past_weeks=2,
        future_weeks=1,
    )

    resolved = resolve_build_range(
        project_yaml=project_path,
        options=options,
        today=date(2026, 3, 24),
    )

    assert resolved == (date(2026, 3, 10), date(2026, 3, 31))


def test_resolve_build_range_uses_project_window(tmp_path: Path) -> None:
    project_path = tmp_path / "committee.yaml"
    _write_project(project_path, start_date="2024-01-01", end_date="2024-03-01")

    resolved = resolve_build_range(
        project_yaml=project_path,
        options=ParsedRangeOptions(None, None, None, None),
    )

    assert resolved == (date(2024, 1, 1), date(2024, 3, 1))


def test_resolve_build_range_defaults_and_warns_when_project_end_missing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    project_path = tmp_path / "committee.yaml"
    _write_project(project_path, start_date="2024-01-01", end_date=None)

    resolved = resolve_build_range(
        project_yaml=project_path,
        options=ParsedRangeOptions(None, None, None, None),
        today=date(2026, 3, 24),
    )

    assert resolved == (date(2026, 3, 17), date(2026, 3, 31))
    assert "2026-03-17" in caplog.text
    assert "2026-03-31" in caplog.text


def test_parse_cli_range_options_rejects_invalid_expression() -> None:
    with pytest.raises(
        typer.BadParameter, match="--from must be a valid date expression"
    ):
        parse_cli_range_options(
            from_date="definitely-not-a-date",
            to_date=None,
            past_weeks=None,
            future_weeks=None,
        )


def test_parse_date_option_accepts_relative_shorthand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "committee_builder.date_parsing.current_datetime",
        lambda: datetime(2026, 3, 24, 15, 0, 0),
    )

    assert parse_date_option("-2w", option_name="--from") == date(2026, 3, 10)


def test_parse_date_expression_accepts_natural_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "committee_builder.date_parsing.current_datetime",
        lambda: datetime(2026, 3, 24, 15, 0, 0),
    )

    assert parse_date_expression("now", label="date_window") == date(2026, 3, 24)


def test_resolve_build_range_accepts_yaml_date_expressions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "committee_builder.date_parsing.current_datetime",
        lambda: datetime(2026, 3, 24, 15, 0, 0),
    )
    project_path = tmp_path / "committee.yaml"
    _write_project(project_path, start_date="-2w", end_date="now")

    resolved = resolve_build_range(
        project_yaml=project_path,
        options=ParsedRangeOptions(None, None, None, None),
    )

    assert resolved == (date(2026, 3, 10), date(2026, 3, 24))
