"""Tests for `committee add minutes` command."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from committee_builder.cli import app

runner = CliRunner()

PROJECT_YAML = """
schema_version: "1.0"
committee:
  name: "Minutes CLI Test"
  start_date: "2024-01-01"
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
    date: "2024-01-10"
    important: true
    summary_md: "Initial"
  - id: "evt-2"
    type: "meeting"
    title: "Repeat"
    date: "2024-02-01"
    important: false
    summary_md: "One"
  - id: "evt-3"
    type: "meeting"
    title: "Repeat"
    date: "2024-03-01"
    important: false
    summary_md: "Two"
"""


def test_add_minutes_successful_embed() -> None:
    with runner.isolated_filesystem():
        project = Path("committee.yaml")
        minutes = Path("minutes.md")
        project.write_text(PROJECT_YAML, encoding="utf-8")
        minutes.write_text("## Minutes\n\n- Approved", encoding="utf-8")

        result = runner.invoke(
            app,
            ["add", "minutes", str(project), "evt-1", str(minutes)],
        )

        assert result.exit_code == 0
        written = yaml.safe_load(project.read_text(encoding="utf-8"))
        assert written["events"][0]["minutes_md"] == "## Minutes\n\n- Approved"


def test_add_minutes_missing_file() -> None:
    with runner.isolated_filesystem():
        project = Path("committee.yaml")
        project.write_text(PROJECT_YAML, encoding="utf-8")

        result = runner.invoke(
            app,
            ["add", "minutes", str(project), "evt-1", "missing.md"],
        )

        assert result.exit_code != 0
        assert "Minutes file not found" in result.output


def test_add_minutes_unknown_event_selector() -> None:
    with runner.isolated_filesystem():
        project = Path("committee.yaml")
        minutes = Path("minutes.md")
        project.write_text(PROJECT_YAML, encoding="utf-8")
        minutes.write_text("content", encoding="utf-8")

        result = runner.invoke(
            app,
            ["add", "minutes", str(project), "evt-404", str(minutes)],
        )

        assert result.exit_code != 0
        assert "No event found for id 'evt-404'" in result.output


def test_add_minutes_ambiguous_title_selector() -> None:
    with runner.isolated_filesystem():
        project = Path("committee.yaml")
        minutes = Path("minutes.md")
        project.write_text(PROJECT_YAML, encoding="utf-8")
        minutes.write_text("content", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "add",
                "minutes",
                str(project),
                "ignored",
                str(minutes),
                "--title",
                "Repeat",
            ],
        )

        assert result.exit_code != 0
        assert "ambiguous; add --date" in result.output


def test_add_minutes_preserves_markdown_newlines() -> None:
    with runner.isolated_filesystem():
        project = Path("committee.yaml")
        minutes = Path("minutes.md")
        project.write_text(PROJECT_YAML, encoding="utf-8")
        markdown = "# Header\n\nParagraph with **bold**.\n\n- a\n- b\n"
        minutes.write_text(markdown, encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "add",
                "minutes",
                str(project),
                "unused-id",
                str(minutes),
                "--title",
                "Kickoff",
                "--date",
                "2024-01-10",
            ],
        )

        assert result.exit_code == 0
        written = yaml.safe_load(project.read_text(encoding="utf-8"))
        assert written["events"][0]["minutes_md"] == markdown


def test_add_minutes_adds_yaml_suffix_when_omitted() -> None:
    with runner.isolated_filesystem():
        project = Path("committee.yaml")
        minutes = Path("minutes.md")
        project.write_text(PROJECT_YAML, encoding="utf-8")
        minutes.write_text("## Minutes\n\n- Approved", encoding="utf-8")

        result = runner.invoke(
            app,
            ["add", "minutes", "committee", "evt-1", str(minutes)],
        )

        assert result.exit_code == 0
        written = yaml.safe_load(project.read_text(encoding="utf-8"))
        assert written["events"][0]["minutes_md"] == "## Minutes\n\n- Approved"
