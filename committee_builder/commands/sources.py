"""Indico source management and meeting generation commands."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import typer

from committee_builder.indico.client import fetch_category_title, fetch_meetings
from committee_builder.indico.config import (
    IndicoConfig,
    IndicoSource,
    load_indico_config,
    save_indico_config,
)
from committee_builder.indico.markdown import html_to_markdown
from committee_builder.io.yaml_io import write_yaml
from committee_builder.pipeline.validate_pipeline import (
    PipelineValidationResult,
    validate_yaml,
)
from committee_builder.schema.models import CommitteeHistory
from committee_builder.schema.validators import validate_semantics

logger = logging.getLogger(__name__)

DEFAULT_API_KEY_ENV = "INDICO_API_KEY"
DEFAULT_API_TOKEN_ENV = "INDICO_API_TOKEN"
DEFAULT_EVENT_TYPE_STYLES = {
    "meeting": {"label": "Meeting", "color": "sky"},
    "report": {"label": "Report", "color": "emerald"},
    "decision": {"label": "Decision", "color": "rose"},
    "milestone": {"label": "Milestone", "color": "amber"},
    "external": {"label": "External", "color": "violet"},
}


@dataclass(frozen=True)
class GeneratePaths:
    project_yaml: Path | None
    output_path: Path | None


def add_source_command(
    config: Path = typer.Argument(
        ..., help="Project config path or project name (adds .yaml if omitted)."
    ),
    category_url: str = typer.Argument(
        ..., help="Full Indico category URL (for example https://host/category/1234/)."
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Optional source title. Defaults to the remote category name.",
    ),
    api_key_env: str = typer.Option(
        DEFAULT_API_KEY_ENV,
        "--api-key-env",
        help="Env var for API key (used when resolving category title).",
    ),
    api_token_env: str = typer.Option(
        DEFAULT_API_TOKEN_ENV,
        "--api-token-env",
        help="Env var for API token (used when resolving category title).",
    ),
) -> None:
    """Add or replace a source in the project config."""
    config_path = _normalize_config_path(config)
    base_url, category_id = _parse_category_url(category_url)
    source_name = title or fetch_category_title(
        base_url=base_url,
        category_id=category_id,
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )

    current = load_indico_config(config_path)
    filtered_sources = [
        source for source in current.sources if source.name != source_name
    ]
    filtered_sources.append(
        IndicoSource(name=source_name, category_id=category_id, base_url=base_url)
    )
    save_indico_config(
        config_path,
        IndicoConfig(version=current.version, sources=filtered_sources),
    )
    logger.info("Saved source '%s' in %s", source_name, config_path)


def list_sources_command(
    config: Path = typer.Argument(
        ..., help="Project config path or project name (adds .yaml if omitted)."
    ),
) -> None:
    """List all configured sources."""
    config_path = _normalize_config_path(config)
    current = load_indico_config(config_path)
    if not current.sources:
        typer.echo("No sources configured.")
        return

    for source in sorted(current.sources, key=lambda item: item.name):
        typer.echo(
            f"{source.name}: category={source.category_id}, base_url={source.base_url}"
        )


def remove_source_command(
    config: Path = typer.Argument(
        ..., help="Project config path or project name (adds .yaml if omitted)."
    ),
    name: str = typer.Argument(..., help="Source name to remove."),
) -> None:
    """Remove a source by name."""
    config_path = _normalize_config_path(config)
    current = load_indico_config(config_path)
    filtered = [source for source in current.sources if source.name != name]
    if len(filtered) == len(current.sources):
        raise typer.BadParameter(f"Source not found: {name}")

    save_indico_config(config_path, IndicoConfig(version=current.version, sources=filtered))
    logger.info("Removed source '%s' from %s", name, config_path)


def generate_sources_command(
    config: Path = typer.Argument(
        ..., help="Project config path or project name (adds .yaml if omitted)."
    ),
    project_yaml: Path | None = typer.Argument(
        None,
        help=(
            "Base committee YAML file. Defaults to <config-stem>-project.yaml when "
            "omitted or when the second positional is used as an output path."
        ),
    ),
    output_path_arg: Path | None = typer.Argument(
        None,
        help="Optional output YAML path.",
    ),
    source: list[str] = typer.Option(
        None, "--source", help="Specific source(s) to include."
    ),
    from_date: str | None = typer.Option(
        None, "--from", help="Inclusive date in YYYY-MM-DD format."
    ),
    to_date: str | None = typer.Option(
        None, "--to", help="Inclusive date in YYYY-MM-DD format."
    ),
    past_weeks: int | None = typer.Option(
        None, "--past-weeks", help="Relative range start."
    ),
    future_weeks: int | None = typer.Option(
        None, "--future-weeks", help="Relative range end."
    ),
    api_key_env: str = typer.Option(
        DEFAULT_API_KEY_ENV, "--api-key-env", help="Env var for API key."
    ),
    api_token_env: str = typer.Option(
        DEFAULT_API_TOKEN_ENV, "--api-token-env", help="Env var for API token."
    ),
    output: Path | None = typer.Option(None, "--output", help="Output YAML path."),
) -> None:
    """Generate a new committee YAML with imported Indico meeting events."""
    config_path = _normalize_config_path(config)
    parsed_from = _parse_iso_date(from_date, option_name="--from")
    parsed_to = _parse_iso_date(to_date, option_name="--to")
    range_start, range_end = _resolve_range(
        parsed_from, parsed_to, past_weeks, future_weeks
    )
    config_data = load_indico_config(config_path)
    selected = _select_sources(config_data, source)
    generate_paths = _resolve_generate_paths(
        config_path=config_path,
        project_yaml=project_yaml,
        output_arg=output_path_arg,
        output_option=output,
    )
    validated = _load_history(
        config_path=config_path,
        config_data=config_data,
        project_yaml=generate_paths.project_yaml,
        range_start=range_start,
        range_end=range_end,
    )
    event_styles = validated.history.event_type_styles

    generated_events: list[dict[str, object]] = []
    for selected_source in selected:
        for meeting in fetch_meetings(
            selected_source,
            range_start,
            range_end,
            api_key_env=api_key_env,
            api_token_env=api_token_env,
        ):
            event_doc: dict[str, object] = {
                "id": f"{selected_source.name}-{meeting.remote_id}",
                "type": "meeting",
                "title": meeting.title,
                "date": meeting.start_datetime.date().isoformat(),
                "important": False,
                "summary_md": html_to_markdown(meeting.description)
                or f"Imported from source `{selected_source.name}`.",
                "participants": meeting.participants,
                "tags": [selected_source.name],
                "documents": [],
            }
            if meeting.url:
                event_doc["documents"] = [{"label": "Event Link", "url": meeting.url}]
            generated_events.append(event_doc)

    generated_events.sort(key=lambda item: (str(item["date"]), str(item["id"])))
    existing_events = [
        event.model_dump(mode="json") for event in validated.history.events
    ]

    merged_events: dict[str, dict[str, object]] = {
        str(event["id"]): event for event in existing_events + generated_events
    }

    output_path = generate_paths.output_path or _default_output_path(
        config_path=config_path,
        project_yaml=generate_paths.project_yaml,
    )
    output_payload = {
        "schema_version": validated.history.schema_version,
        "committee": validated.history.committee.model_dump(mode="json"),
        "event_type_styles": {
            event_type.value: event_style.model_dump(mode="json")
            for event_type, event_style in event_styles.items()
        },
        "events": [merged_events[event_id] for event_id in sorted(merged_events)],
    }
    write_yaml(output_path, output_payload)
    logger.info(
        "Generated %s with %s imported meetings", output_path, len(generated_events)
    )


def _resolve_generate_paths(
    config_path: Path,
    project_yaml: Path | None,
    output_arg: Path | None,
    output_option: Path | None,
) -> GeneratePaths:
    inferred_project = config_path.with_name(f"{config_path.stem}-project.yaml")

    if output_option is not None and output_arg is not None:
        raise typer.BadParameter("Use either positional OUTPUT_YAML or --output, not both.")

    if project_yaml is None:
        if inferred_project.exists():
            return GeneratePaths(project_yaml=inferred_project, output_path=output_option)
        return GeneratePaths(project_yaml=None, output_path=output_option)

    if project_yaml.exists():
        return GeneratePaths(project_yaml=project_yaml, output_path=output_arg or output_option)

    if inferred_project.exists():
        return GeneratePaths(project_yaml=inferred_project, output_path=project_yaml)

    if output_arg is not None:
        raise typer.BadParameter(f"Base committee YAML not found: {project_yaml}")

    return GeneratePaths(project_yaml=None, output_path=project_yaml or output_option)


def _load_history(
    config_path: Path,
    config_data: IndicoConfig,
    project_yaml: Path | None,
    range_start: date,
    range_end: date,
) -> PipelineValidationResult:
    if project_yaml is not None:
        return validate_yaml(project_yaml)

    committee_name = (
        config_data.sources[0].name if len(config_data.sources) == 1 else config_path.stem
    )
    history = CommitteeHistory.model_validate(
        {
            "schema_version": "1.0",
            "committee": {
                "name": committee_name,
                "subtitle": "Imported Indico meetings",
                "description_md": f"Generated from Indico source config `{config_path.name}`.",
                "start_date": range_start.isoformat(),
                "end_date": range_end.isoformat(),
            },
            "event_type_styles": DEFAULT_EVENT_TYPE_STYLES,
            "events": [],
        }
    )
    semantic = validate_semantics(history)
    return PipelineValidationResult(history=history, warnings=semantic.warnings)


def _default_output_path(config_path: Path, project_yaml: Path | None) -> Path:
    if project_yaml is not None:
        return project_yaml.with_name(f"{project_yaml.stem}-meetings.yaml")
    return config_path.with_name(f"{config_path.stem}-generated.yaml")


def _normalize_config_path(config: Path) -> Path:
    if config.suffix:
        return config
    return config.with_suffix(".yaml")


def _parse_category_url(category_url: str) -> tuple[str, int]:
    parsed = urlparse(category_url)
    if not parsed.scheme or not parsed.netloc:
        raise typer.BadParameter(
            f"Invalid category URL '{category_url}'. Include scheme and host."
        )

    match = re.search(r"^(?P<prefix>.*?)/category/(?P<id>\d+)(?:/|$)", parsed.path)
    if not match:
        raise typer.BadParameter(
            "Category URL must include '/category/<id>' in the path."
        )

    prefix = match.group("prefix").rstrip("/")
    base_url = f"{parsed.scheme}://{parsed.netloc}{prefix}"
    category_id = int(match.group("id"))
    return base_url, category_id


def _resolve_range(
    from_date: date | None,
    to_date: date | None,
    past_weeks: int | None,
    future_weeks: int | None,
) -> tuple[date, date]:
    has_absolute = from_date is not None or to_date is not None
    has_relative = past_weeks is not None or future_weeks is not None

    if has_absolute and has_relative:
        raise typer.BadParameter(
            "Use either --from/--to or --past-weeks/--future-weeks, not both."
        )

    if has_absolute:
        if from_date is None or to_date is None:
            raise typer.BadParameter(
                "Both --from and --to are required for absolute ranges."
            )
        if to_date < from_date:
            raise typer.BadParameter("--to cannot be before --from.")
        return from_date, to_date

    current_day = date.today()
    effective_past_weeks = past_weeks or 0
    effective_future_weeks = future_weeks or 0
    start = current_day - timedelta(weeks=effective_past_weeks)
    end = current_day + timedelta(weeks=effective_future_weeks)
    if end < start:
        raise typer.BadParameter("Computed relative range is invalid.")
    return start, end


def _parse_iso_date(value: str | None, option_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid date for {option_name}: {value}") from exc


def _select_sources(config: IndicoConfig, names: list[str]) -> list[IndicoSource]:
    if not config.sources:
        raise typer.BadParameter(
            "No sources configured. Run `committee indico add` first."
        )
    if not names:
        return config.sources

    source_lookup = {source.name: source for source in config.sources}
    missing_sources = sorted(name for name in names if name not in source_lookup)
    if missing_sources:
        raise typer.BadParameter(f"Unknown source(s): {', '.join(missing_sources)}")
    return [source_lookup[name] for name in names]
