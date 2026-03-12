"""Tests for Indico source management and generation commands."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from committee_builder.cli import app
from committee_builder.indico.client import IndicoMeeting
from committee_builder.indico import client as indico_client_module

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

        list_result = runner.invoke(app, ["indico", "list", str(config)])
        assert list_result.exit_code == 0
        assert "cern: category=42" in list_result.stdout

        remove_result = runner.invoke(
            app, ["indico", "remove", str(config), "cern"]
        )
        assert remove_result.exit_code == 0

        empty_result = runner.invoke(app, ["indico", "list", str(config)])
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
            ["indico", "list", "my-project"],
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
                str(config_path),
                str(project_path),
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


def test_build_auth_falls_back_to_unauthenticated_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INDICO_API_KEY", raising=False)
    monkeypatch.delenv("INDICO_API_TOKEN", raising=False)

    auth = indico_client_module._build_auth(
        request_url="https://indico.example.com/export/categ/77.json",
        params={"from": "today"},
        api_key_env="INDICO_API_KEY",
        api_token_env="INDICO_API_TOKEN",
    )

    assert auth == {"params": {}, "headers": {}}


def test_build_auth_uses_credentials_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INDICO_API_KEY", "key")
    monkeypatch.setenv("INDICO_API_TOKEN", "token")
    monkeypatch.setattr(indico_client_module.time, "time", lambda: 1234567890)

    auth = indico_client_module._build_auth(
        request_url="https://indico.example.com/export/categ/77.json",
        params={"from": "today"},
        api_key_env="INDICO_API_KEY",
        api_token_env="INDICO_API_TOKEN",
    )

    assert auth["params"]["ak"] == "key"
    assert auth["params"]["timestamp"] == "1234567890"
    assert "signature" in auth["params"]
    assert auth["headers"] == {}


def test_normalize_record_supports_cern_indico_start_date_dict() -> None:
    meeting = indico_client_module._normalize_record(
        {
            "id": "1001",
            "title": "Weekly Coordination",
            "description": "Imported agenda",
            "url": "https://indico.example.com/event/1001",
            "startDate": {
                "date": "2024-05-10",
                "time": "09:30:00",
                "tz": "Europe/Zurich",
            },
        }
    )

    assert meeting.remote_id == "1001"
    assert meeting.title == "Weekly Coordination"
    assert meeting.start_datetime == datetime(2024, 5, 10, 9, 30)


def test_indico_client_dummy_without_dependency() -> None:
    """Dummy test to ensure environments without indico-client still pass test suite."""
    pytest.importorskip("indico")


