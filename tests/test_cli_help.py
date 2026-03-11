"""CLI help and command registration tests."""

from typer.testing import CliRunner

from committee_builder.cli import app


runner = CliRunner()


def test_root_help_has_expected_text() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "build" in result.stdout
    assert "validate" in result.stdout
    assert "--verbose" in result.stdout


def test_build_help_has_options() -> None:
    result = runner.invoke(app, ["build", "--help"])
    assert result.exit_code == 0
    assert "--output" in result.stdout
    assert "--overwrite" in result.stdout
