"""Tests for source management via the add/indico command tree."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
import typer
from typer.testing import CliRunner

from committee_builder.cli import app
from committee_builder.indico.client import IndicoAuthError
from committee_builder.indico.config import load_indico_config
from committee_builder.indico.credentials import api_key_env_name
from committee_builder.commands.sources import _normalize_source_color

runner = CliRunner()


def test_add_indico_creates_source_then_indico_list_and_remove_manage_it() -> None:
    with runner.isolated_filesystem():
        add_result = runner.invoke(
            app,
            [
                "add",
                "indico",
                "project",
                "https://indico.example.com/category/42/",
                "--title",
                "cern",
            ],
        )
        assert add_result.exit_code == 0

        list_result = runner.invoke(app, ["indico", "list", "project"])
        assert list_result.exit_code == 0
        assert "cern: category=42" in list_result.stdout

        remove_result = runner.invoke(app, ["indico", "remove", "project", "cern"])
        assert remove_result.exit_code == 0

        empty_result = runner.invoke(app, ["indico", "list", "project"])
        assert empty_result.exit_code == 0
        assert "No sources configured." in empty_result.stdout


def test_indico_add_accumulates_title_match_and_title_exclude() -> None:
    with runner.isolated_filesystem():
        first_result = runner.invoke(
            app,
            [
                "indico",
                "add",
                "project",
                "https://indico.example.com/category/42/",
                "--title",
                "cern",
                "--title-match",
                "LUP",
                "--title-exclude",
                "high school",
            ],
        )
        second_result = runner.invoke(
            app,
            [
                "indico",
                "add",
                "project",
                "https://indico.example.com/category/42/",
                "--title",
                "cern",
                "--title-match",
                "Plenary",
                "--title-exclude",
                "students",
            ],
        )
        assert first_result.exit_code == 0
        assert second_result.exit_code == 0

        config = load_indico_config(Path("project.yaml"))
        assert config.sources[0].title_matches == ["LUP", "Plenary"]
        assert config.sources[0].title_exclude_patterns == ["high school", "students"]


def test_indico_add_uses_remote_title_when_not_supplied(
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

        list_result = runner.invoke(app, ["indico", "list", "my-project"])
        assert list_result.exit_code == 0
        assert "ATLAS: category=77" in list_result.stdout


def test_indico_add_reports_auth_error_for_protected_category(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setattr(
            "committee_builder.commands.sources.fetch_category_title",
            lambda **_kwargs: (_ for _ in ()).throw(IndicoAuthError("auth required")),
        )

        with caplog.at_level("ERROR"):
            result = runner.invoke(
                app,
                [
                    "add",
                    "indico",
                    "atlas",
                    "https://indico.example.com/category/77/",
                ],
            )

        assert result.exit_code != 0
        assert "auth required" in caplog.text


def test_indico_api_key_creates_and_updates_local_dotenv() -> None:
    with runner.isolated_filesystem():
        base_url = "https://indico.example.com/indico/"
        env_name = api_key_env_name(base_url)

        first_result = runner.invoke(app, ["indico", "api-key", base_url, "first-key"])
        assert first_result.exit_code == 0
        assert Path(".env").read_text(encoding="utf-8") == f"{env_name}=first-key\n"

        second_result = runner.invoke(
            app,
            ["indico", "api-key", "https://indico.example.com/indico", "updated-key"],
        )
        assert second_result.exit_code == 0
        assert Path(".env").read_text(encoding="utf-8") == f"{env_name}=updated-key\n"


def test_indico_add_normalizes_named_color() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "indico",
                "add",
                "colors",
                "https://indico.example.com/category/77/",
                "--title",
                "ATLAS",
                "--color",
                "red",
            ],
        )
        assert result.exit_code == 0

        config_data = yaml.safe_load(Path("colors.yaml").read_text(encoding="utf-8"))
        assert config_data["indico_category_sources"][0][
            "color"
        ] == _normalize_source_color("red")


def test_normalize_source_color_accepts_webcolors_name() -> None:
    assert _normalize_source_color("darkslategrey") == _normalize_source_color(
        "#2f4f4f"
    )


def test_normalize_source_color_rejects_unknown_name() -> None:
    with pytest.raises(typer.BadParameter, match="Unsupported color"):
        _normalize_source_color("not-a-real-color")


def test_add_event_adds_yaml_suffix_when_omitted() -> None:
    with runner.isolated_filesystem():
        Path("project.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "1.0",
                    "metadata": {"name": "Project"},
                    "date_window": {
                        "start_date": "2023-01-01",
                        "end_date": "2023-01-31",
                    },
                    "event_type_styles": {},
                    "events": [],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "add",
                "event",
                "project",
                "--title",
                "Kickoff",
                "--date",
                "2023-01-10",
            ],
        )

        assert result.exit_code == 0
        written = yaml.safe_load(Path("project.yaml").read_text(encoding="utf-8"))
        assert written["events"][0]["title"] == "Kickoff"


def test_validate_adds_yaml_suffix_when_omitted() -> None:
    with runner.isolated_filesystem():
        Path("project.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "1.0",
                    "metadata": {"name": "Project"},
                    "date_window": {
                        "start_date": "2023-01-01",
                        "end_date": "2023-01-31",
                    },
                    "event_type_styles": {},
                    "events": [],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(app, ["validate", "project"])

        assert result.exit_code == 0
