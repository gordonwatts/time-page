"""Indico source management and meeting generation commands."""

from __future__ import annotations

import logging
import re
from colorsys import hls_to_rgb
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

import typer

from committee_builder.indico.client import (
    IndicoContribution,
    IndicoDocument,
    IndicoAuthError,
    fetch_category_title,
    fetch_meetings,
)
from committee_builder.indico.config import (
    IndicoConfig,
    IndicoSource,
    load_indico_config,
    save_indico_config,
)
from committee_builder.indico.credentials import normalize_base_url, store_api_key
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
NAMED_COLORS = {
    "aliceblue": "#f0f8ff",
    "antiquewhite": "#faebd7",
    "aqua": "#00ffff",
    "aquamarine": "#7fffd4",
    "azure": "#f0ffff",
    "beige": "#f5f5dc",
    "bisque": "#ffe4c4",
    "black": "#000000",
    "blanchedalmond": "#ffebcd",
    "blue": "#0000ff",
    "blueviolet": "#8a2be2",
    "brown": "#a52a2a",
    "burlywood": "#deb887",
    "cadetblue": "#5f9ea0",
    "chartreuse": "#7fff00",
    "chocolate": "#d2691e",
    "coral": "#ff7f50",
    "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc",
    "crimson": "#dc143c",
    "cyan": "#00ffff",
    "darkblue": "#00008b",
    "darkcyan": "#008b8b",
    "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9",
    "darkgreen": "#006400",
    "darkgrey": "#a9a9a9",
    "darkkhaki": "#bdb76b",
    "darkmagenta": "#8b008b",
    "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00",
    "darkorchid": "#9932cc",
    "darkred": "#8b0000",
    "darksalmon": "#e9967a",
    "darkseagreen": "#8fbc8f",
    "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f",
    "darkslategrey": "#2f4f4f",
    "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3",
    "deeppink": "#ff1493",
    "deepskyblue": "#00bfff",
    "dimgray": "#696969",
    "dimgrey": "#696969",
    "dodgerblue": "#1e90ff",
    "firebrick": "#b22222",
    "floralwhite": "#fffaf0",
    "forestgreen": "#228b22",
    "fuchsia": "#ff00ff",
    "gainsboro": "#dcdcdc",
    "ghostwhite": "#f8f8ff",
    "gold": "#ffd700",
    "goldenrod": "#daa520",
    "gray": "#808080",
    "green": "#008000",
    "greenyellow": "#adff2f",
    "grey": "#808080",
    "honeydew": "#f0fff0",
    "hotpink": "#ff69b4",
    "indianred": "#cd5c5c",
    "indigo": "#4b0082",
    "ivory": "#fffff0",
    "khaki": "#f0e68c",
    "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5",
    "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd",
    "lightblue": "#add8e6",
    "lightcoral": "#f08080",
    "lightcyan": "#e0ffff",
    "lightgoldenrodyellow": "#fafad2",
    "lightgray": "#d3d3d3",
    "lightgreen": "#90ee90",
    "lightgrey": "#d3d3d3",
    "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa",
    "lightskyblue": "#87cefa",
    "lightslategray": "#778899",
    "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0",
    "lime": "#00ff00",
    "limegreen": "#32cd32",
    "linen": "#faf0e6",
    "magenta": "#ff00ff",
    "maroon": "#800000",
    "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd",
    "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db",
    "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a",
    "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585",
    "midnightblue": "#191970",
    "mintcream": "#f5fffa",
    "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead",
    "navy": "#000080",
    "oldlace": "#fdf5e6",
    "olive": "#808000",
    "olivedrab": "#6b8e23",
    "orange": "#ffa500",
    "orangered": "#ff4500",
    "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98",
    "paleturquoise": "#afeeee",
    "palevioletred": "#db7093",
    "papayawhip": "#ffefd5",
    "peachpuff": "#ffdab9",
    "peru": "#cd853f",
    "pink": "#ffc0cb",
    "plum": "#dda0dd",
    "powderblue": "#b0e0e6",
    "purple": "#800080",
    "red": "#ff0000",
    "rosybrown": "#bc8f8f",
    "royalblue": "#4169e1",
    "saddlebrown": "#8b4513",
    "salmon": "#fa8072",
    "sandybrown": "#f4a460",
    "seagreen": "#2e8b57",
    "seashell": "#fff5ee",
    "sienna": "#a0522d",
    "silver": "#c0c0c0",
    "skyblue": "#87ceeb",
    "slateblue": "#6a5acd",
    "slategray": "#708090",
    "slategrey": "#708090",
    "snow": "#fffafa",
    "springgreen": "#00ff7f",
    "steelblue": "#4682b4",
    "tan": "#d2b48c",
    "teal": "#008080",
    "thistle": "#d8bfd8",
    "tomato": "#ff6347",
    "turquoise": "#40e0d0",
    "violet": "#ee82ee",
    "wheat": "#f5deb3",
    "white": "#ffffff",
    "whitesmoke": "#f5f5f5",
    "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
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
    color: str | None = typer.Option(
        None,
        "--color",
        help="Optional feed color. Accepts hex (#RRGGBB or #RGB) or CSS color names.",
    ),
    title_match: list[str] | None = typer.Option(
        None,
        "--title-match",
        help=(
            "Optional case-insensitive regex used to keep meetings by title. "
            "Repeat to add multiple patterns."
        ),
    ),
    title_exclude: list[str] | None = typer.Option(
        None,
        "--title-exclude",
        help=(
            "Optional case-insensitive regex used to skip meetings by title. "
            "Repeat to add multiple patterns."
        ),
    ),
) -> None:
    """Add or replace a source in the project config."""
    config_path = _normalize_config_path(config)
    base_url, category_id = _parse_category_url(category_url)
    try:
        source_name = title or fetch_category_title(
            base_url=base_url,
            category_id=category_id,
            api_key_env=api_key_env,
            api_token_env=api_token_env,
        )
    except IndicoAuthError as exc:
        logger.error("%s", exc)
        raise

    current = load_indico_config(config_path)
    current_source = next(
        (source for source in current.sources if source.name == source_name),
        None,
    )
    source_color = (
        _normalize_source_color(color)
        if color is not None
        else current_source.color
        if current_source is not None
        else _assign_unique_source_color(current.sources)
    )
    title_matches = _merge_title_matches(
        current_source.title_matches if current_source is not None else [],
        _normalize_title_match_patterns(title_match or []),
    )
    title_exclude_patterns = _merge_title_patterns(
        current_source.title_exclude_patterns if current_source is not None else [],
        _normalize_title_patterns(
            title_exclude or [],
            option_name="--title-exclude",
        ),
    )
    filtered_sources = [
        source for source in current.sources if source.name != source_name
    ]
    filtered_sources.append(
        IndicoSource(
            name=source_name,
            category_id=category_id,
            base_url=base_url,
            color=source_color,
            title_matches=title_matches,
            title_exclude_patterns=title_exclude_patterns,
        )
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
        match_summary = (
            f", title_matches=[{', '.join(source.title_matches)}]"
            if source.title_matches
            else ""
        )
        exclude_summary = (
            f", title_exclude=[{', '.join(source.title_exclude_patterns)}]"
            if source.title_exclude_patterns
            else ""
        )
        typer.echo(
            f"{source.name}: category={source.category_id}, base_url={source.base_url}, "
            f"color={source.color}{match_summary}{exclude_summary}"
        )


def api_key_command(
    base_url: str = typer.Argument(..., help="Indico base URL."),
    key: str = typer.Argument(..., help="API key to store for the base URL."),
) -> None:
    """Create or update the local .env file with an Indico API key."""
    try:
        normalized_base_url = normalize_base_url(base_url)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    env_path = store_api_key(normalized_base_url, key)
    logger.info("Stored API key for %s in %s", normalized_base_url, env_path)


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
        try:
            meetings = fetch_meetings(
                selected_source,
                range_start,
                range_end,
                api_key_env=api_key_env,
                api_token_env=api_token_env,
            )
        except IndicoAuthError as exc:
                logger.warning(
                    "Skipping source '%s': %s",
                    selected_source.name,
                    exc,
                )
                continue

        meetings = [
            meeting
            for meeting in meetings
            if _meeting_matches_title_patterns(
                meeting.title, selected_source.title_matches
            )
        ]

        for meeting in meetings:
            if _meeting_matches_title_exclusions(meeting.title, selected_source.title_exclude_patterns):
                continue
            interesting_contributions = _contributions_with_documents(
                meeting.contributions
            )
            is_interesting_meeting = bool(meeting.documents or interesting_contributions)
            summary_md = (
                html_to_markdown(meeting.description, base_url=selected_source.base_url)
                or ""
            )
            minutes_md = (
                html_to_markdown(meeting.minutes, base_url=selected_source.base_url)
                or ""
            )
            if meeting.url:
                indico_link = f"[Link To Indico]({meeting.url})"
                summary_md = (
                    f"{indico_link}\n\n{summary_md.lstrip()}"
                    if summary_md.strip()
                    else indico_link
                )
            contribution_table = _build_contribution_table(meeting.contributions)
            if contribution_table:
                summary_md = (
                    f"{summary_md.rstrip()}\n\n{contribution_table}"
                    if summary_md.strip()
                    else contribution_table
                )
            event_doc: dict[str, object] = {
                "id": f"{selected_source.name}-{meeting.remote_id}",
                "type": "meeting",
                "title": meeting.title,
                "date": meeting.start_datetime.date().isoformat(),
                "important": is_interesting_meeting,
                "short_label": _build_meeting_short_label(interesting_contributions),
                "summary_md": summary_md
                or f"Imported from source `{selected_source.name}`.",
                "minutes_md": minutes_md or None,
                "participants": meeting.participants,
                "tags": [],
                "documents": [
                    {
                        "label": document.label,
                        "url": document.url,
                        "talk_title": document.talk_title,
                        "speaker_names": document.speaker_names,
                    }
                    for document in meeting.documents
                ],
                "contributions": [
                    {
                        "title": contribution.title,
                        "speaker_names": contribution.speaker_names,
                        "documents": [
                            {
                                "label": document.label,
                                "url": document.url,
                                "talk_title": document.talk_title,
                                "speaker_names": document.speaker_names,
                            }
                            for document in contribution.documents
                        ],
                        "minutes_md": (
                            html_to_markdown(
                                contribution.minutes,
                                base_url=selected_source.base_url,
                            )
                            or None
                        ),
                    }
                    for contribution in meeting.contributions
                ],
                "source_name": selected_source.name,
                "source_color": selected_source.color,
            }
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

    prefix = match.group("prefix")
    base_url = normalize_base_url(f"{parsed.scheme}://{parsed.netloc}{prefix}")
    category_id = int(match.group("id"))
    return base_url, category_id


def _normalize_source_color(value: str) -> str:
    hex_color = _parse_color_to_hex(value)
    pale_color = _blend_rgb(_hex_to_rgb(hex_color), 0.78)
    return _rgb_to_hex(pale_color)


def _normalize_title_patterns(values: list[str], *, option_name: str) -> list[str]:
    patterns: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            continue
        try:
            re.compile(normalized, flags=re.IGNORECASE)
        except re.error as exc:
            raise typer.BadParameter(
                f"Invalid title pattern for {option_name} '{value}': {exc}"
            ) from exc
        folded = normalized.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        patterns.append(normalized)
    return patterns


def _normalize_title_match_patterns(values: list[str]) -> list[str]:
    return _normalize_title_patterns(values, option_name="--title-match")


def _merge_title_patterns(existing: list[str], additions: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*existing, *additions]:
        folded = value.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        merged.append(value)
    return merged


def _merge_title_matches(existing: list[str], additions: list[str]) -> list[str]:
    return _merge_title_patterns(existing, additions)


def _meeting_matches_title_exclusions(title: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in patterns)


def _assign_unique_source_color(existing_sources: list[IndicoSource]) -> str:
    used_colors = {source.color.lower() for source in existing_sources}
    golden_ratio = 0.61803398875
    for index in range(1, 512):
        hue = (index * golden_ratio) % 1.0
        red, green, blue = hls_to_rgb(hue, 0.62, 0.55)
        candidate = _rgb_to_hex(
            _blend_rgb(
                (round(red * 255), round(green * 255), round(blue * 255)),
                0.78,
            )
        )
        if candidate.lower() not in used_colors:
            return candidate
    raise typer.BadParameter("Unable to assign a unique source color.")


def _parse_color_to_hex(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).lower()
    if re.fullmatch(r"#[0-9a-f]{3}", normalized):
        return "#" + "".join(component * 2 for component in normalized[1:])
    if re.fullmatch(r"#[0-9a-f]{6}", normalized):
        return normalized
    named = NAMED_COLORS.get(normalized)
    if named is not None:
        return named
    raise typer.BadParameter(
        f"Unsupported color '{value}'. Use #RGB, #RRGGBB, or a CSS color name."
    )


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    return (
        int(value[1:3], 16),
        int(value[3:5], 16),
        int(value[5:7], 16),
    )


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _blend_rgb(rgb: tuple[int, int, int], weight_to_white: float) -> tuple[int, int, int]:
    clamped_weight = max(0.0, min(1.0, weight_to_white))
    return tuple(
        round(channel + (255 - channel) * clamped_weight) for channel in rgb
    )


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


def _meeting_matches_title_patterns(title: str, title_patterns: list[str]) -> bool:
    if not title_patterns:
        return True
    return any(
        re.search(pattern, title, flags=re.IGNORECASE) for pattern in title_patterns
    )


def _build_contribution_table(contributions: list[IndicoContribution]) -> str:
    if not contributions:
        return ""

    rows = [
        "| Talk | Speakers | Documents |",
        "| --- | --- | --- |",
    ]
    for contribution in sorted(contributions, key=lambda item: item.sort_key):
        authors = ", ".join(contribution.speaker_names) if contribution.speaker_names else "-"
        if contribution.documents:
            document_labels = _build_document_link_labels(contribution.documents)
            documents = "<br>".join(
                f"• [{_escape_markdown_table_cell(label)}]({document.url})"
                for document, label in zip(contribution.documents, document_labels, strict=True)
            )
        else:
            documents = "-"
        rows.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown_table_cell(_short_contribution_title(contribution)),
                    _escape_markdown_table_cell(authors),
                    documents.replace("|", "\\|"),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _build_document_link_labels(documents: list[IndicoDocument]) -> list[str]:
    if not documents:
        return []
    if len(documents) == 1:
        return ["Talk"]

    normalized_labels = [
        re.sub(r"\s+", " ", document.label).strip() or f"Upload {index + 1}"
        for index, document in enumerate(documents)
    ]
    return _compact_unique_labels(normalized_labels)


def _compact_unique_labels(labels: list[str], *, initial_width: int = 20) -> list[str]:
    if not labels:
        return []

    maximum_width = max(len(label) for label in labels)
    minimum_width = min(initial_width, maximum_width)

    for width in range(minimum_width, maximum_width + 1):
        shortened = [label if len(label) <= width else label[:width] for label in labels]
        if len(set(shortened)) != len(shortened):
            continue

        rolled_back = [
            _roll_back_to_word_boundary(label, width) for label in labels
        ]
        if len(set(rolled_back)) == len(rolled_back):
            return rolled_back

        duplicates = {
            value for value in rolled_back if rolled_back.count(value) > 1
        }
        return [
            shortened[index] if value in duplicates else value
            for index, value in enumerate(rolled_back)
        ]

    duplicate_counts: dict[str, int] = {}
    unique_labels: list[str] = []
    for label in labels:
        count = duplicate_counts.get(label, 0) + 1
        duplicate_counts[label] = count
        unique_labels.append(label if count == 1 else f"{label} ({count})")
    return unique_labels


def _roll_back_to_word_boundary(value: str, width: int) -> str:
    if len(value) <= width:
        return value

    truncated = value[:width]
    last_space = truncated.rfind(" ")
    if last_space <= 0:
        return truncated
    return truncated[:last_space]


def _contributions_with_documents(
    contributions: list[IndicoContribution],
) -> list[IndicoContribution]:
    return [
        contribution for contribution in contributions if contribution.documents
    ]


def _build_meeting_short_label(
    contributions: list[IndicoContribution],
    *,
    limit: int = 3,
) -> str | None:
    if not contributions:
        return None

    titles: list[str] = []
    for contribution in sorted(contributions, key=lambda item: item.sort_key):
        title = re.sub(r"\s+", " ", contribution.title).strip() or "Untitled talk"
        if title not in titles:
            titles.append(title)

    if not titles:
        return None

    visible = titles[:limit]
    remaining = len(titles) - len(visible)
    summary = "; ".join(visible)
    if remaining > 0:
        summary = f"{summary}; +{remaining} more"
    return summary


def _escape_markdown_table_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().replace("|", "\\|")


def _short_contribution_title(contribution: IndicoContribution) -> str:
    normalized_title = re.sub(r"\s+", " ", contribution.title).strip()
    if normalized_title:
        return normalized_title

    if not contribution.documents:
        return "Untitled talk"

    source = contribution.documents[0].label
    shortened = _short_title_from_label(source, contribution.speaker_names)
    return shortened or "Untitled talk"


def _short_title_from_label(label: str, speaker_names: list[str]) -> str:
    stem = Path(label).stem
    stem = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", stem)
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"\b\d{6,8}\b", " ", stem)
    stem = re.sub(r"\b(?:amgmeeting|amg)\b", " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\bcopy\b", " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\b\d+\b(?=\s*$)", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()

    for speaker_name in speaker_names:
        speaker_pattern = re.sub(r"\s+", " ", speaker_name).strip()
        if not speaker_pattern:
            continue
        stem = re.sub(
            rf"\b{re.escape(speaker_pattern)}\b\s*$",
            "",
            stem,
            flags=re.IGNORECASE,
        ).strip()

    return re.sub(r"\s+", " ", stem).strip()


def _looks_like_identifier_title(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return True
    if re.fullmatch(r"[A-Z0-9!._/-]+", normalized):
        return True
    words = [word for word in re.split(r"\s+", normalized) if word]
    if len(words) == 1 and len(re.findall(r"[A-Za-z]", normalized)) <= 8:
        return True
    return False
