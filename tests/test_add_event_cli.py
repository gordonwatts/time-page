"""Tests for `committee add event` command."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from committee_builder.cli import app

runner = CliRunner()

PROJECT_YAML = """
schema_version: "1.0"
metadata:
  name: "Add Event CLI Test"
date_window:
  start_date: "2024-01-01"
  end_date: "2024-12-31"
event_type_styles:
  meeting: {label: "Meeting", color: "sky"}
  report: {label: "Report", color: "emerald"}
  decision: {label: "Decision", color: "rose"}
  milestone: {label: "Milestone", color: "amber"}
  external: {label: "External", color: "violet"}
events: []
"""


def test_add_event_uses_date_in_generated_title_when_title_omitted() -> None:
    with runner.isolated_filesystem():
        project = Path("committee.yaml")
        project.write_text(PROJECT_YAML, encoding="utf-8")

        result = runner.invoke(app, ["add", "event", str(project), "--date", "2024-04-15"])

        assert result.exit_code == 0
        written = yaml.safe_load(project.read_text(encoding="utf-8"))
        assert written["events"][0]["title"] == "2024-04-15 - Event Title"


def test_add_event_preserves_explicit_title() -> None:
    with runner.isolated_filesystem():
        project = Path("committee.yaml")
        project.write_text(PROJECT_YAML, encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "add",
                "event",
                str(project),
                "--date",
                "2024-04-15",
                "--title",
                "Detector Readout Review",
            ],
        )

        assert result.exit_code == 0
        written = yaml.safe_load(project.read_text(encoding="utf-8"))
        assert written["events"][0]["title"] == "Detector Readout Review"
