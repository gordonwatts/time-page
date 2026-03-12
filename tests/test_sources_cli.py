"""Tests for Indico source management and generation commands."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from committee_builder.cli import app
from committee_builder.indico.client import IndicoMeeting

runner = CliRunner()

BASE_PROJECT = """
schema_version: "1.0"
committee:
  name: "Source Test"
  start_date: "2023-01-01"
event_type_styles:
  meeting: {label: "Meeting", color: "sky"}
  report: {label: "Report", color: "emerald"}
  decision: {label: "Decision", color: "rose"}
  milestone: {label: "Milestone", color: "amber"}
  external: {label: "External", color: "violet"}
events: []
"""


def test_indico_add_list_remove() -> None:
    with runner.isolated_filesystem():
        config = Path("project")

        add_result = runner.invoke(
            app,
            [
                "indico",
                "add",
                str(config),
                "https://indico.example.com/category/42/",
                "--title",
                "cern",
            ],
        )
        assert add_result.exit_code == 0

        list_result = runner.invoke(app, ["indico", "list", "--config", str(config)])
        assert list_result.exit_code == 0
        assert "cern: category=42" in list_result.stdout

        remove_result = runner.invoke(
            app, ["indico", "remove", "cern", "--config", str(config)]
        )
        assert remove_result.exit_code == 0

        empty_result = runner.invoke(app, ["indico", "list", "--config", str(config)])
        assert empty_result.exit_code == 0
        assert "No sources configured." in empty_result.stdout


def test_indico_add_uses_category_title_when_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setattr(
            "committee_builder.commands.sources.fetch_category_title",
            lambda **_kwargs: "ATLAS",
        )

        result = runner.invoke(
            app,
            [
                "indico",
                "add",
                "my-project",
                "https://indico.example.com/indico/category/77/",
            ],
        )
        assert result.exit_code == 0

        list_result = runner.invoke(
            app,
            ["indico", "list", "--config", "my-project"],
        )
        assert list_result.exit_code == 0
        assert "ATLAS: category=77, base_url=https://indico.example.com/indico" in list_result.stdout


def test_indico_generate_merges_imported_meetings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with runner.isolated_filesystem():
        project_path = Path("project.yaml")
        project_path.write_text(BASE_PROJECT, encoding="utf-8")

        config_path = Path("sources")
        add_result = runner.invoke(
            app,
            [
                "indico",
                "add",
                str(config_path),
                "https://indico.example.com/category/11/",
                "--title",
                "atlas",
            ],
        )
        assert add_result.exit_code == 0

        def fake_fetch(*_args: object, **_kwargs: object) -> list[IndicoMeeting]:
            return [
                IndicoMeeting(
                    remote_id="1001",
                    title="Weekly Coordination",
                    start_datetime=datetime(2024, 5, 10, 9, 30),
                    description="Imported agenda",
                    url="https://indico.example.com/event/1001",
                )
            ]

        monkeypatch.setattr(
            "committee_builder.commands.sources.fetch_meetings", fake_fetch
        )

        output_path = Path("generated.yaml")
        result = runner.invoke(
            app,
            [
                "indico",
                "generate",
                str(project_path),
                "--config",
                str(config_path),
                "--from",
                "2024-05-01",
                "--to",
                "2024-05-31",
                "--output",
                str(output_path),
            ],
        )
        assert result.exit_code == 0
        assert output_path.exists()

        rendered = output_path.read_text(encoding="utf-8")
        assert "atlas-1001" in rendered
        assert "Weekly Coordination" in rendered


def test_indico_add_requires_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["indico", "add", "https://indico.example.com/category/11/"],
        )
        assert result.exit_code == 2


def test_indico_client_dummy_without_dependency() -> None:
    """Dummy test to ensure environments without indico-client still pass test suite."""
    pytest.importorskip("indico_client")


