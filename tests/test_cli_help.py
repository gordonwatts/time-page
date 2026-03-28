"""CLI help and command registration tests."""

from typer.testing import CliRunner

from committee_builder.cli import app


runner = CliRunner()


def test_root_help_has_expected_text() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "build" in result.stdout
    assert "validate" in result.stdout
    assert "add" in result.stdout
    assert "indico" in result.stdout
    assert "--verbose" in result.stdout


def test_build_help_has_range_and_output_options() -> None:
    result = runner.invoke(app, ["build", "--help"])
    assert result.exit_code == 0
    assert "--output" in result.stdout
    assert "--overwrite" in result.stdout
    assert "--from" in result.stdout
    assert "--to" in result.stdout
    assert "--past-weeks" in result.stdout
    assert "--future-weeks" in result.stdout


def test_add_help_has_new_command_tree() -> None:
    result = runner.invoke(app, ["add", "--help"])
    assert result.exit_code == 0
    assert "event" in result.stdout
    assert "indico" in result.stdout
    assert "minutes" in result.stdout


def test_add_indico_help_has_expected_options() -> None:
    result = runner.invoke(app, ["add", "indico", "--help"])
    assert result.exit_code == 0
    assert "--title" in result.stdout


def test_indico_add_help_has_advanced_source_options() -> None:
    result = runner.invoke(app, ["indico", "add", "--help"])
    assert result.exit_code == 0
    assert "--color" in result.stdout
    assert "--title-match" in result.stdout
    assert "--title-exclude" in result.stdout


def test_indico_help_has_list_remove_and_api_key() -> None:
    result = runner.invoke(app, ["indico", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "remove" in result.stdout
    assert "api-key" in result.stdout
    assert "generate" not in result.stdout


def test_indico_generate_command_is_unregistered() -> None:
    result = runner.invoke(app, ["indico", "generate", "--help"])
    assert result.exit_code != 0
    assert "No such command 'generate'" in result.output
