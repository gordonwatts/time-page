"""Typer CLI entrypoint for committee history generation."""

from __future__ import annotations

import logging

import typer

from committee_builder.commands.build import build_command
from committee_builder.commands.import_csv import import_csv_command
from committee_builder.commands.import_md import import_md_command
from committee_builder.commands.init import init_command
from committee_builder.commands.sources import (
    add_source_command,
    generate_sources_command,
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
      committee validate data/committee.history.yaml
      committee build data/committee.history.yaml
      committee -vv build data/committee.history.yaml --overwrite
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
app.command("import-csv", help="Placeholder for future CSV import workflow.")(
    import_csv_command
)
app.command("import-md", help="Placeholder for future markdown import workflow.")(
    import_md_command
)

indico_app = typer.Typer(
    help="Manage Indico category sources and generate imported meetings."
)
indico_app.command("add", help="Add an Indico source to the project config.")(
    add_source_command
)
indico_app.command("list", help="List configured Indico sources.")(
    list_sources_command
)
indico_app.command("remove", help="Remove an Indico source from the config.")(
    remove_source_command
)
indico_app.command("generate", help="Generate meetings YAML from configured sources.")(
    generate_sources_command
)

app.add_typer(indico_app, name="indico")


def main() -> None:
    """Console script entrypoint."""
    app()


if __name__ == "__main__":
    main()
