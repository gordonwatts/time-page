"""Tests for Indico source management and generation commands."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from committee_builder.cli import app
from committee_builder.indico.client import (
    IndicoContribution,
    IndicoDocument,
    IndicoAuthError,
    IndicoMeeting,
)
from committee_builder.indico import client as indico_client_module
from committee_builder.commands.sources import (
    GeneratePaths,
    _build_document_link_labels,
    _compact_unique_labels,
    _normalize_source_color,
    _resolve_generate_paths,
    _short_contribution_title,
)
from committee_builder.indico.credentials import api_key_env_name

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

        config_data = yaml.safe_load(config.with_suffix(".yaml").read_text(encoding="utf-8"))
        assert config_data["sources"][0]["color"].startswith("#")

        list_result = runner.invoke(app, ["indico", "list", str(config)])
        assert list_result.exit_code == 0
        assert "cern: category=42" in list_result.stdout
        assert "color=" in list_result.stdout

        remove_result = runner.invoke(
            app, ["indico", "remove", str(config), "cern"]
        )
        assert remove_result.exit_code == 0

        empty_result = runner.invoke(app, ["indico", "list", str(config)])
        assert empty_result.exit_code == 0
        assert "No sources configured." in empty_result.stdout


def test_indico_api_key_creates_and_updates_local_dotenv() -> None:
    with runner.isolated_filesystem():
        base_url = "https://indico.example.com/indico/"
        env_name = api_key_env_name(base_url)

        first_result = runner.invoke(
            app, ["indico", "api-key", base_url, "first-key"]
        )
        assert first_result.exit_code == 0
        assert Path(".env").read_text(encoding="utf-8") == f"{env_name}=first-key\n"

        second_result = runner.invoke(
            app, ["indico", "api-key", "https://indico.example.com/indico", "updated-key"]
        )
        assert second_result.exit_code == 0
        assert Path(".env").read_text(encoding="utf-8") == f"{env_name}=updated-key\n"


def test_indico_api_key_preserves_existing_entries() -> None:
    with runner.isolated_filesystem():
        Path(".env").write_text(
            "# existing\nOTHER_VAR=1\n\nUNCHANGED=yes\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["indico", "api-key", "https://indico.example.com", "secret"],
        )
        assert result.exit_code == 0

        content = Path(".env").read_text(encoding="utf-8")
        assert "# existing" in content
        assert "OTHER_VAR=1" in content
        assert "UNCHANGED=yes" in content
        assert f"{api_key_env_name('https://indico.example.com')}=secret" in content


def test_indico_api_key_stores_multiple_base_urls() -> None:
    with runner.isolated_filesystem():
        first_url = "https://indico.example.com"
        second_url = "https://indico.example.com/indico"

        first_result = runner.invoke(app, ["indico", "api-key", first_url, "first"])
        second_result = runner.invoke(app, ["indico", "api-key", second_url, "second"])

        assert first_result.exit_code == 0
        assert second_result.exit_code == 0

        content = Path(".env").read_text(encoding="utf-8")
        assert f"{api_key_env_name(first_url)}=first" in content
        assert f"{api_key_env_name(second_url)}=second" in content


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
        assert "ATLAS: category=77, base_url=https://indico.example.com/indico, color=" in list_result.stdout


def test_indico_add_logs_auth_error_for_protected_category(
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
                    "indico",
                    "add",
                    "atlas",
                    "https://indico.example.com/category/77/",
                ],
            )

        assert result.exit_code != 0
        assert "auth required" in caplog.text


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
        assert config_data["sources"][0]["color"] == _normalize_source_color("red")


def test_indico_add_normalizes_hex_color() -> None:
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
                "#88ccff",
            ],
        )
        assert result.exit_code == 0

        config_data = yaml.safe_load(Path("colors.yaml").read_text(encoding="utf-8"))
        assert config_data["sources"][0]["color"] == _normalize_source_color("#88ccff")


def test_indico_add_assigns_unique_generated_colors() -> None:
    with runner.isolated_filesystem():
        first = runner.invoke(
            app,
            [
                "indico",
                "add",
                "colors",
                "https://indico.example.com/category/11/",
                "--title",
                "ATLAS",
            ],
        )
        second = runner.invoke(
            app,
            [
                "indico",
                "add",
                "colors",
                "https://indico.example.com/category/12/",
                "--title",
                "CMS",
            ],
        )
        assert first.exit_code == 0
        assert second.exit_code == 0

        config_data = yaml.safe_load(Path("colors.yaml").read_text(encoding="utf-8"))
        colors = [source["color"] for source in config_data["sources"]]
        assert len(colors) == len(set(colors))


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
                    participants=["Jane Doe"],
                    documents=[
                        IndicoDocument(
                            label="slides.pdf",
                            url="https://indico.example.com/files/slides.pdf",
                        )
                    ],
                    contributions=[
                        IndicoContribution(
                            title="Weekly Coordination",
                            speaker_names=["Jane Doe"],
                            documents=[
                                IndicoDocument(
                                    label="slides.pdf",
                                    url="https://indico.example.com/files/slides.pdf",
                                )
                            ],
                        )
                    ],
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
        parsed = yaml.safe_load(rendered)
        event = parsed["events"][0]
        assert "atlas-1001" in rendered
        assert "Weekly Coordination" in rendered
        assert event["important"] is True
        assert event["short_label"] == "Weekly Coordination"
        assert event["source_name"] == "atlas"
        assert event["source_color"].startswith("#")
        assert event["tags"] == []
        assert "[Link To Indico](https://indico.example.com/event/1001)" in rendered
        assert "slides.pdf" in rendered
        assert "https://indico.example.com/files/slides.pdf" in rendered
        assert "Event Link" not in rendered


def test_indico_generate_converts_html_descriptions_to_markdown(
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
                    description=(
                        "<p>Hello <strong>team</strong>.</p>"
                        "<p>Agenda:</p>"
                        "<ul><li>Updates</li><li><em>Risks</em></li></ul>"
                    ),
                    minutes=(
                        "<p><strong>Minutes approved.</strong></p>"
                        '<p><img src="/event/1001/attachments/7/8/plot.png" alt="plot"></p>'
                        "<ul><li>Action one</li><li>Action two</li></ul>"
                    ),
                    participants=["Jane Doe", "John Roe"],
                    documents=[
                        IndicoDocument(
                            label="slides.pdf",
                            url="https://indico.example.com/files/slides.pdf",
                        )
                    ],
                    contributions=[
                        IndicoContribution(
                            title="Weekly Coordination",
                            speaker_names=["Jane Doe", "John Roe"],
                            minutes="<p>Talk note with <em>formatting</em>.</p>",
                            documents=[
                                IndicoDocument(
                                    label="slides.pdf",
                                    url="https://indico.example.com/files/slides.pdf",
                                )
                            ],
                        )
                    ],
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

        rendered = output_path.read_text(encoding="utf-8")
        assert "<p>" not in rendered
        assert "Hello **team**." in rendered
        assert "[Link To Indico](https://indico.example.com/event/1001)" in rendered
        assert "- Updates" in rendered
        assert "- *Risks*" in rendered
        assert "minutes_md:" in rendered
        assert "Minutes approved." in rendered
        assert "![plot](https://indico.example.com/event/1001/attachments/7/8/plot.png)" in rendered
        assert "- Action one" in rendered
        assert "Talk note with *formatting*." in rendered
        assert "| Talk | Speakers | Documents |" in rendered
        assert "• [Talk](https://indico.example.com/files/slides.pdf)" in rendered
        assert "- Jane Doe" in rendered
        assert "- John Roe" in rendered


def test_indico_generate_marks_meeting_interesting_when_talk_files_exist(
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
                    participants=["Jane Doe", "John Roe", "Alex Poe"],
                    documents=[],
                    contributions=[
                        IndicoContribution(
                            title="Calibration update",
                            speaker_names=["Jane Doe"],
                            documents=[
                                IndicoDocument(
                                    label="calibration.pdf",
                                    url="https://indico.example.com/files/calibration.pdf",
                                )
                            ],
                            sort_key=(0, 0),
                        ),
                        IndicoContribution(
                            title="Detector status",
                            speaker_names=["John Roe"],
                            documents=[
                                IndicoDocument(
                                    label="status.pdf",
                                    url="https://indico.example.com/files/status.pdf",
                                )
                            ],
                            sort_key=(1, 0),
                        ),
                        IndicoContribution(
                            title="Open discussion",
                            speaker_names=["Alex Poe"],
                            documents=[],
                            sort_key=(2, 0),
                        ),
                    ],
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

        rendered = output_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(rendered)
        event = parsed["events"][0]
        assert event["important"] is True
        assert event["short_label"] == "Calibration update; Detector status"


def test_indico_generate_keeps_meeting_collapsed_without_talk_files(
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
                    participants=["Jane Doe"],
                    documents=[],
                    contributions=[
                        IndicoContribution(
                            title="Calibration update",
                            speaker_names=["Jane Doe"],
                            documents=[],
                        )
                    ],
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

        rendered = output_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(rendered)
        event = parsed["events"][0]
        assert event["important"] is False
        assert "short_label" not in event


def test_indico_generate_marks_meeting_interesting_when_only_agenda_documents_exist(
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
                    participants=["Jane Doe"],
                    documents=[
                        IndicoDocument(
                            label="agenda.pdf",
                            url="https://indico.example.com/files/agenda.pdf",
                        )
                    ],
                    contributions=[],
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

        rendered = output_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(rendered)
        event = parsed["events"][0]
        assert event["important"] is True
        assert "agenda.pdf" in rendered
        assert "short_label" not in event


def test_indico_generate_logs_warning_and_skips_source_on_auth_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
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

        monkeypatch.setattr(
            "committee_builder.commands.sources.fetch_meetings",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                IndicoAuthError("auth required")
            ),
        )

        output_path = Path("generated.yaml")
        with caplog.at_level("WARNING"):
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
        assert "Skipping source 'atlas': auth required" in caplog.text
        parsed = yaml.safe_load(output_path.read_text(encoding="utf-8"))
        assert parsed["events"] == []


def test_resolve_generate_paths_treats_missing_second_arg_as_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = Path("atlas.yaml")
    inferred_project = Path("atlas-project.yaml")

    monkeypatch.setattr(
        Path,
        "exists",
        lambda self: self == inferred_project,
    )

    resolved = _resolve_generate_paths(
        config_path=config_path,
        project_yaml=Path("atlas-generated.yaml"),
        output_arg=None,
        output_option=None,
    )

    assert resolved == GeneratePaths(
        project_yaml=inferred_project,
        output_path=Path("atlas-generated.yaml"),
    )


def test_resolve_generate_paths_uses_generated_defaults_without_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "exists", lambda self: False)

    resolved = _resolve_generate_paths(
        config_path=Path("atlas.yaml"),
        project_yaml=Path("atlas-generated.yaml"),
        output_arg=None,
        output_option=None,
    )

    assert resolved == GeneratePaths(
        project_yaml=None,
        output_path=Path("atlas-generated.yaml"),
    )


def test_indico_add_requires_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            ["indico", "add", "https://indico.example.com/category/11/"],
        )
        assert result.exit_code == 2


def test_indico_config_missing_color_fails() -> None:
    with runner.isolated_filesystem():
        Path("broken.yaml").write_text(
            'version: "1"\nsources:\n  - name: "ATLAS"\n    category_id: 77\n    base_url: "https://indico.example.com"\n',
            encoding="utf-8",
        )

        result = runner.invoke(app, ["indico", "list", "broken"])
        assert result.exit_code != 0
        assert result.exception is not None
        assert "color" in str(result.exception)


def test_build_auth_falls_back_to_unauthenticated_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with runner.isolated_filesystem():
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


def test_build_auth_loads_api_key_from_local_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with runner.isolated_filesystem():
        monkeypatch.delenv("INDICO_API_KEY", raising=False)
        monkeypatch.delenv("INDICO_API_TOKEN", raising=False)
        Path(".env").write_text(
            f"{api_key_env_name('https://indico.example.com/indico')}=dotenv-key\n",
            encoding="utf-8",
        )

        auth = indico_client_module._build_auth(
            request_url="https://indico.example.com/indico/export/categ/77.json",
            params={"from": "today"},
            api_key_env="INDICO_API_KEY",
            api_token_env="INDICO_API_TOKEN",
        )

        assert auth["params"] == {}
        assert auth["headers"] == {"Authorization": "Bearer dotenv-key"}


def test_build_auth_uses_exact_normalized_base_url_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with runner.isolated_filesystem():
        monkeypatch.delenv("INDICO_API_KEY", raising=False)
        monkeypatch.delenv("INDICO_API_TOKEN", raising=False)
        Path(".env").write_text(
            f"{api_key_env_name('https://indico.example.com')}=host-key\n",
            encoding="utf-8",
        )

        auth = indico_client_module._build_auth(
            request_url="https://indico.example.com/indico/export/categ/77.json",
            params={"from": "today"},
            api_key_env="INDICO_API_KEY",
            api_token_env="INDICO_API_TOKEN",
        )

        assert auth == {"params": {}, "headers": {}}


def test_build_auth_prefers_explicit_env_over_local_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with runner.isolated_filesystem():
        monkeypatch.setenv("INDICO_API_KEY", "explicit-key")
        monkeypatch.delenv("INDICO_API_TOKEN", raising=False)
        Path(".env").write_text(
            f"{api_key_env_name('https://indico.example.com')}=dotenv-key\n",
            encoding="utf-8",
        )

        auth = indico_client_module._build_auth(
            request_url="https://indico.example.com/export/categ/77.json",
            params={"from": "today"},
            api_key_env="INDICO_API_KEY",
            api_token_env="INDICO_API_TOKEN",
        )

        assert auth["params"]["ak"] == "explicit-key"


def test_build_auth_prefers_explicit_token_env_over_local_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with runner.isolated_filesystem():
        monkeypatch.delenv("INDICO_API_KEY", raising=False)
        monkeypatch.setenv("INDICO_API_TOKEN", "explicit-token")
        Path(".env").write_text(
            f"{api_key_env_name('https://indico.example.com')}=dotenv-key\n",
            encoding="utf-8",
        )

        auth = indico_client_module._build_auth(
            request_url="https://indico.example.com/export/categ/77.json",
            params={"from": "today"},
            api_key_env="INDICO_API_KEY",
            api_token_env="INDICO_API_TOKEN",
        )

        assert auth["params"] == {}
        assert auth["headers"] == {"Authorization": "Bearer explicit-token"}


def test_fetch_category_page_title_reads_standard_indico_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        text = "<html><head><title>Long Lived Particle Forum · Indico</title></head></html>"
        url = "https://indico.cern.ch/category/2636/"
        status_code = 200
        content = text.encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(
        indico_client_module,
        "_build_auth",
        lambda **_kwargs: {"params": {}, "headers": {}},
    )
    monkeypatch.setattr(
        indico_client_module.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(),
    )

    assert (
        indico_client_module._fetch_category_page_title(
            "https://indico.cern.ch",
            2636,
            "INDICO_API_KEY",
            "INDICO_API_TOKEN",
        )
        == "Long Lived Particle Forum"
    )


def test_fetch_category_page_title_accepts_mojibake_middle_dot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        text = "<html><head><title>Long Lived Particle Forum Â· Indico</title></head></html>"
        url = "https://indico.cern.ch/category/2636/"
        status_code = 200
        content = text.encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(
        indico_client_module,
        "_build_auth",
        lambda **_kwargs: {"params": {}, "headers": {}},
    )
    monkeypatch.setattr(
        indico_client_module.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(),
    )

    assert (
        indico_client_module._fetch_category_page_title(
            "https://indico.cern.ch",
            2636,
            "INDICO_API_KEY",
            "INDICO_API_TOKEN",
        )
        == "Long Lived Particle Forum"
    )


def test_normalize_record_supports_cern_indico_start_date_dict() -> None:
    meeting = indico_client_module._normalize_record(
        {
            "id": "1001",
            "title": "Weekly Coordination",
            "description": "Imported agenda",
            "url": "https://indico.example.com/event/1001",
            "chairs": [
                {
                    "fullName": "Doe, Jane",
                }
            ],
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
    assert meeting.participants == ["Jane Doe"]


def test_extract_participants_collects_chairs_and_contribution_speakers() -> None:
    participants = indico_client_module._extract_participants(
        {
            "chairs": [
                {"fullName": "Plehn, Tilman"},
            ],
            "contributions": [
                {
                    "title": "Talk",
                    "speakers": [
                        {"fullName": "Roe, John"},
                        {"first_name": "Jane", "last_name": "Doe"},
                    ],
                }
            ],
        }
    )

    assert participants == ["Tilman Plehn", "John Roe", "Jane Doe"]


def test_extract_documents_collects_attachment_links() -> None:
    documents = indico_client_module._extract_documents(
        """
        <div class="material-list">
          <a class="attachment icon-file-pdf i-button"
             href="/event/1638970/attachments/3236500/5771268/cern_26.pdf"
             title="cern_26.pdf">cern_26.pdf</a>
          <a class="attachment icon-link i-button"
             href="https://videos.cern.ch/record/3021230"
             title="Recording">Recording</a>
        </div>
        """,
        base_url="https://indico.cern.ch",
    )

    assert documents == [
        IndicoDocument(
            label="cern_26.pdf",
            url="https://indico.cern.ch/event/1638970/attachments/3236500/5771268/cern_26.pdf",
        ),
        IndicoDocument(
            label="Recording",
            url="https://videos.cern.ch/record/3021230",
        ),
    ]


def test_extract_contribution_documents_keeps_talk_context() -> None:
    documents = indico_client_module._extract_contribution_documents(
        {
            "contributions": [
                {
                    "title": "Calibration update",
                    "speakers": [{"fullName": "Doe, Jane"}],
                    "attachments": [
                        {
                            "filename": "calibration.pdf",
                            "download_url": "/event/1001/attachments/1/2/calibration.pdf",
                        }
                    ],
                }
            ]
        },
        base_url="https://indico.cern.ch",
    )

    assert documents == [
        IndicoDocument(
            label="calibration.pdf",
            url="https://indico.cern.ch/event/1001/attachments/1/2/calibration.pdf",
            talk_title="Calibration update",
            speaker_names=["Jane Doe"],
        )
    ]


def test_extract_contribution_documents_sorts_by_contribution_order() -> None:
    documents = indico_client_module._extract_contribution_documents(
        {
            "contributions": [
                {
                    "id": "200",
                    "title": "Second talk",
                    "speakers": [{"fullName": "Roe, John"}],
                    "attachments": [
                        {
                            "filename": "second.pdf",
                            "download_url": "/event/1001/attachments/1/2/second.pdf",
                        }
                    ],
                },
                {
                    "id": "100",
                    "title": "Introduction",
                    "speakers": [{"fullName": "Doe, Jane"}],
                    "attachments": [
                        {
                            "filename": "intro.pdf",
                            "download_url": "/event/1001/attachments/1/2/intro.pdf",
                        }
                    ],
                },
            ]
        },
        base_url="https://indico.cern.ch",
    )

    assert [document.talk_title for document in documents] == [
        "Introduction",
        "Second talk",
    ]


def test_extract_contributions_keeps_talk_rows_without_documents() -> None:
    contributions = indico_client_module._extract_contributions(
        {
            "contributions": [
                {
                    "id": "100",
                    "title": "Introduction",
                    "speakers": [{"fullName": "Doe, Jane"}],
                }
            ]
        },
        base_url="https://indico.cern.ch",
    )

    assert contributions == [
        indico_client_module.IndicoContribution(
            title="Introduction",
            speaker_names=["Jane Doe"],
            documents=[],
            sort_key=(0, 0),
        )
    ]


def test_extract_meeting_minutes_prefers_explicit_minutes_field() -> None:
    minutes = indico_client_module._extract_minutes(
        {
            "description": "<p>Agenda</p>",
            "minutes": {"html": "<p><strong>Approved</strong> minutes.</p>"},
            "contributions": [
                {"title": "Talk", "note": {"html": "<p>Talk note</p>"}},
            ],
        }
    )

    assert minutes == "<p><strong>Approved</strong> minutes.</p>"


def test_extract_contribution_minutes_reads_note_payload() -> None:
    contributions = indico_client_module._extract_contributions(
        {
            "contributions": [
                {
                    "id": "100",
                    "title": "Introduction",
                    "speakers": [{"fullName": "Doe, Jane"}],
                    "note": {"content": "<p>Discussed calibration strategy.</p>"},
                }
            ]
        },
        base_url="https://indico.cern.ch",
    )

    assert contributions == [
        indico_client_module.IndicoContribution(
            title="Introduction",
            speaker_names=["Jane Doe"],
            documents=[],
            minutes="<p>Discussed calibration strategy.</p>",
            sort_key=(0, 0),
        )
    ]


def test_merge_documents_prefers_contextual_entry_for_same_label() -> None:
    merged = indico_client_module._merge_documents(
        [
            IndicoDocument(
                label="ATLTOPDPD-1463",
                url="https://indico.cern.ch/event/1661706/contributions/6985305/attachments/3234887/5767988/go",
                talk_title="Parton level information in PHYS",
                speaker_names=["Davide Melini"],
                sort_key=(0, 1, 0),
            )
        ],
        [
            IndicoDocument(
                label="ATLTOPDPD-1463",
                url="https://its.cern.ch/jira/browse/ATLTOPDPD-1463",
                talk_title=None,
                speaker_names=[],
            )
        ],
    )

    assert merged == [
        IndicoDocument(
            label="ATLTOPDPD-1463",
            url="https://its.cern.ch/jira/browse/ATLTOPDPD-1463",
            talk_title="Parton level information in PHYS",
            speaker_names=["Davide Melini"],
            sort_key=(0, 1, 0),
        )
    ]


def test_short_contribution_title_prefers_indico_contribution_title() -> None:
    contribution = IndicoContribution(
        title="Lossy compression for FTAG branches",
        speaker_names=["Romain Bouquet"],
        documents=[
            IndicoDocument(
                label="AMGMeeting_LossyCompressionStudiesInFTAG_20260227_RomainBouquet-1.pdf",
                url="https://example.org/slides.pdf",
            )
        ],
    )

    assert _short_contribution_title(contribution) == "Lossy compression for FTAG branches"


def test_short_contribution_title_falls_back_to_cleaned_filename() -> None:
    contribution = IndicoContribution(
        title="",
        speaker_names=["Romain Bouquet"],
        documents=[
            IndicoDocument(
                label="AMGMeeting_LossyCompressionStudiesInFTAG_20260227_RomainBouquet-1.pdf",
                url="https://example.org/slides.pdf",
            )
        ],
    )

    assert _short_contribution_title(contribution) == "Lossy Compression Studies In FTAG"


def test_short_contribution_title_uses_placeholder_without_title_or_documents() -> None:
    contribution = IndicoContribution(title="", speaker_names=["Romain Bouquet"], documents=[])

    assert _short_contribution_title(contribution) == "Untitled talk"


def test_build_document_link_labels_uses_talk_for_single_upload() -> None:
    labels = _build_document_link_labels(
        [IndicoDocument(label="Very long filename.pdf", url="https://example.org/slides.pdf")]
    )

    assert labels == ["Talk"]


def test_compact_unique_labels_truncates_at_word_boundary_when_possible() -> None:
    labels = _compact_unique_labels(
        ["First very long upload name.pdf", "Second very long upload name.pdf"]
    )

    assert labels == ["First very long", "Second very long"]


def test_compact_unique_labels_extends_until_unique() -> None:
    labels = _compact_unique_labels(
        ["Common prefix upload alpha.pdf", "Common prefix upload beta.pdf"]
    )

    assert labels == ["Common prefix upload a", "Common prefix upload b"]


def test_compact_unique_labels_reverts_colliding_word_boundary_rollbacks() -> None:
    labels = _compact_unique_labels(
        [
            "Alpha beta one file.pdf",
            "Alpha beta one note.pdf",
            "Gamma delta report long.pdf",
        ]
    )

    assert labels == ["Alpha beta one file.", "Alpha beta one note.", "Gamma delta report"]


def test_indico_client_dummy_without_dependency() -> None:
    """Dummy test to ensure environments without indico-client still pass test suite."""
    pytest.importorskip("indico")


