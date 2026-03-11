"""Build command tests."""

from pathlib import Path

from typer.testing import CliRunner

from committee_builder.cli import app


runner = CliRunner()

SAMPLE = """
schema_version: "1.0"
committee:
  name: "CLI Test"
  start_date: "2023-01-01"
event_type_styles:
  meeting: {label: "Meeting", color: "sky"}
  report: {label: "Report", color: "emerald"}
  decision: {label: "Decision", color: "rose"}
  milestone: {label: "Milestone", color: "amber"}
  external: {label: "External", color: "violet"}
events:
  - id: "evt-1"
    type: "meeting"
    title: "Kickoff"
    date: "2023-01-10"
    important: true
    summary_md: "Hello"
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
        assert "CLI Test" in text
