"""Tests for Indico source management and generation commands."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from committee_builder.cli import app
from committee_builder.indico.client import IndicoMeeting
from committee_builder.indico import client as indico_client_module
from committee_builder.commands.sources import GeneratePaths, _resolve_generate_paths
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
                    participants=["Jane Doe"],
                    documents=[("slides.pdf", "https://indico.example.com/files/slides.pdf")],
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
        assert "slides.pdf" in rendered
        assert "https://indico.example.com/files/slides.pdf" in rendered


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
                    participants=["Jane Doe", "John Roe"],
                    documents=[("slides.pdf", "https://indico.example.com/files/slides.pdf")],
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
        assert "- Updates" in rendered
        assert "- *Risks*" in rendered
        assert "- Jane Doe" in rendered
        assert "- John Roe" in rendered


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
        (
            "cern_26.pdf",
            "https://indico.cern.ch/event/1638970/attachments/3236500/5771268/cern_26.pdf",
        ),
        (
            "Recording",
            "https://videos.cern.ch/record/3021230",
        ),
    ]


def test_indico_client_dummy_without_dependency() -> None:
    """Dummy test to ensure environments without indico-client still pass test suite."""
    pytest.importorskip("indico")


