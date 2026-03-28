"""Indico source management and meeting generation commands."""

from __future__ import annotations

import logging
import re
from colorsys import hls_to_rgb
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import typer

from committee_builder.indico.client import (
    IndicoAuthError,
    fetch_category_title,
)
from committee_builder.indico.credentials import normalize_base_url, store_api_key
from committee_builder.io.yaml_io import (
    load_project_file,
    save_project_file,
)
from committee_builder.schema.models import IndicoSource, ProjectFile

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

    current = _load_or_init_project(config_path)
    current_source = next(
        (
            source
            for source in current.indico_category_sources
            if source.name == source_name
        ),
        None,
    )
    source_color = (
        _normalize_source_color(color)
        if color is not None
        else (
            current_source.color
            if current_source is not None
            else _assign_unique_source_color(current.indico_category_sources)
        )
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
        source
        for source in current.indico_category_sources
        if source.name != source_name
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
    save_project_file(
        config_path,
        current.model_copy(
            update={
                "indico_category_sources": sorted(
                    filtered_sources, key=lambda source: source.name.casefold()
                )
            }
        ),
    )
    logger.info("Saved source '%s' in %s", source_name, config_path)


def list_sources_command(
    config: Path = typer.Argument(
        ..., help="Project config path or project name (adds .yaml if omitted)."
    ),
) -> None:
    """List all configured sources."""
    config_path = _normalize_config_path(config)
    current = _load_or_init_project(config_path)
    if not current.indico_category_sources:
        typer.echo("No sources configured.")
        return

    for source in sorted(
        current.indico_category_sources, key=lambda item: item.name.casefold()
    ):
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
    current = _load_or_init_project(config_path)
    filtered = [
        source for source in current.indico_category_sources if source.name != name
    ]
    if len(filtered) == len(current.indico_category_sources):
        raise typer.BadParameter(f"Source not found: {name}")

    save_project_file(
        config_path,
        current.model_copy(
            update={
                "indico_category_sources": sorted(
                    filtered, key=lambda source: source.name.casefold()
                )
            }
        ),
    )
    logger.info("Removed source '%s' from %s", name, config_path)


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


def _blend_rgb(
    rgb: tuple[int, int, int], weight_to_white: float
) -> tuple[int, int, int]:
    clamped_weight = max(0.0, min(1.0, weight_to_white))
    return tuple(round(channel + (255 - channel) * clamped_weight) for channel in rgb)


def _load_or_init_project(config_path: Path) -> ProjectFile:
    if config_path.exists():
        return load_project_file(config_path)
    return _build_default_project(config_path.stem)


def _build_default_project(project_name: str) -> ProjectFile:
    today = date.today()
    return ProjectFile.model_validate(
        {
            "schema_version": "1.0",
            "metadata": {"name": project_name},
            "date_window": {"start_date": today.isoformat(), "end_date": None},
            "event_type_styles": DEFAULT_EVENT_TYPE_STYLES,
            "events": [],
            "indico_category_sources": [],
        }
    )
