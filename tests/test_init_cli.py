"""Tests for the init command."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from committee_builder.cli import app

runner = CliRunner()


def test_init_creates_blank_valid_project_yaml() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init", "project.yaml"])

        assert result.exit_code == 0

        payload = yaml.safe_load(Path("project.yaml").read_text(encoding="utf-8"))
        assert payload == {
            "schema_version": "1.0",
            "metadata": {"name": "Committee Project"},
            "date_window": {
                "start_date": "2023-01-01",
                "end_date": "2024-12-31",
            },
            "event_type_styles": {},
            "events": [],
        }

