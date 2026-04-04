"""Build command tests."""

from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from committee_builder.cli import app


runner = CliRunner()

SAMPLE = """
schema_version: "1.0"
metadata:
  name: "CLI Test"
date_window:
  start_date: "2023-01-01"
  end_date: "2023-01-31"
event_type_styles:
  meeting: {label: "Meeting", color: "sky"}
  report: {label: "Report", color: "emerald"}
  decision: {label: "Decision", color: "rose"}
  milestone: {label: "Milestone", color: "amber"}
  external: {label: "External", color: "violet"}
events:
  - id: "evt-1"
    type: "meeting"
    title: "January Kickoff"
    date: "2023-01-10"
    important: true
    summary_md: "Hello"
  - id: "evt-2"
    type: "meeting"
    title: "February Planning"
    date: "2023-02-10"
    important: false
    summary_md: "Outside default range"
"""


def test_build_default_output_path() -> None:
    with runner.isolated_filesystem():
        src = Path("committee.yaml")
        src.write_text(SAMPLE, encoding="utf-8")

        result = runner.invoke(app, ["build", str(src)])
        assert result.exit_code == 0

        out = Path("committee.html")
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert "committee-data" in text
        assert "January Kickoff" in text
        assert "February Planning" not in text


def test_build_cli_absolute_dates_override_project_window() -> None:
    with runner.isolated_filesystem():
        src = Path("committee.yaml")
        src.write_text(SAMPLE, encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "build",
                str(src),
                "--from",
                "2023-02-01",
                "--to",
                "2023-02-28",
            ],
        )
        assert result.exit_code == 0

        text = Path("committee.html").read_text(encoding="utf-8")
        assert "January Kickoff" not in text
        assert "February Planning" in text


def test_build_accepts_flexible_date_expressions(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "committee_builder.date_parsing.current_datetime",
        lambda: datetime(2023, 2, 10, 12, 0, 0),
    )
    with runner.isolated_filesystem():
        src = Path("committee.yaml")
        src.write_text(SAMPLE, encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "build",
                str(src),
                "--from",
                "-1d",
                "--to",
                "now",
            ],
        )
        assert result.exit_code == 0

        text = Path("committee.html").read_text(encoding="utf-8")
        assert "January Kickoff" not in text
        assert "February Planning" in text


def test_build_rejects_mixing_absolute_and_relative_range_flags() -> None:
    with runner.isolated_filesystem():
        src = Path("committee.yaml")
        src.write_text(SAMPLE, encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "build",
                str(src),
                "--from",
                "2023-01-01",
                "--to",
                "2023-01-31",
                "--past-weeks",
                "2",
            ],
        )
        assert result.exit_code != 0
        assert "Use either --from/--to or --past-weeks/--future-weeks" in result.output


def test_build_adds_yaml_suffix_when_omitted() -> None:
    with runner.isolated_filesystem():
        Path("committee.yaml").write_text(SAMPLE, encoding="utf-8")

        result = runner.invoke(app, ["build", "committee"])

        assert result.exit_code == 0
        assert Path("committee.html").exists()
