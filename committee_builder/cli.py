"""Typer CLI entrypoint for committee history generation."""

from __future__ import annotations

import logging

import typer

from committee_builder.commands.add import (
    add_event_command,
    add_indico_category_command,
    add_minutes_command,
)
from committee_builder.commands.build import build_command
from committee_builder.commands.init import init_command
from committee_builder.commands.sources import (
    add_source_command,
    api_key_command,
    list_sources_command,
    remove_source_command,
)
from committee_builder.commands.validate import validate_command
from committee_builder.logging_config import configure_logging

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="committee",
    help=(
        "Build and validate committee history YAML data, then generate "
        "a standalone self-contained HTML timeline page."
    ),
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main_callback(
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase logging verbosity (-v for INFO, -vv for DEBUG).",
    )
) -> None:
    """Committee history tooling.

    Examples:
      committee init project.yaml --title "Steering Committee" --from 2024-01-01 --to 2025-12-31
      committee add event project.yaml --title "Kickoff" --date 2024-01-12
      committee build project.yaml --from 2024-01-01 --to 2024-12-31
    """
    configure_logging(verbose)
    logger.debug("CLI initialized with verbosity=%s", verbose)


app.command("build", help="Generate a standalone HTML page from a YAML source file.")(
    build_command
)
app.command(
    "validate", help="Validate a YAML source file against schema and semantic checks."
)(validate_command)
app.command("init", help="Create a starter YAML source file.")(init_command)

add_app = typer.Typer(help="Add events, Indico categories, and minutes content.")
add_app.command("event", help="Add a local event entry to project YAML.")(
    add_event_command
)
add_app.command("indico", help="Add an Indico category source to project config.")(
    add_indico_category_command
)
add_app.command(
    "minutes",
    help="Import minutes text file content into markdown fields in YAML.",
)(add_minutes_command)
app.add_typer(add_app, name="add")

indico_app = typer.Typer(help="Manage Indico categories and local API credentials.")
indico_app.command("add", help="Add an Indico category to the project config.")(
    add_source_command
)
indico_app.command("list", help="List configured Indico categories.")(
    list_sources_command
)
indico_app.command(
    "api-key",
    help=(
        "Store an Indico API key in the local .env file.\n\n"
        "After logging into Indico, select 'My Profile' from your login dropdown, "
        "then click the settings button. In the left navigation bar, open "
        "'API Tokens', create a token, and paste it here. The base URL is the "
        "site base URL, for example https://indico.cern.ch for CERN."
    ),
)(api_key_command)
indico_app.command("remove", help="Remove an Indico category from the config.")(
    remove_source_command
)
app.add_typer(indico_app, name="indico")


def main() -> None:
    """Console script entrypoint."""
    app()


if __name__ == "__main__":
    main()
