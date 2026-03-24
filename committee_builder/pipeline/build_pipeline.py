"""Build pipeline for standalone HTML generation."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from committee_builder.io.normalize import normalize_history
from committee_builder.io.paths import default_output_html
from committee_builder.pipeline.validate_pipeline import validate_yaml
from committee_builder.render.markdown import render_markdown
from committee_builder.schema.models import DateWindow, ProjectFile


def _render_payload(history) -> dict:
    payload = history.model_dump(mode="json")
    metadata = payload["metadata"]
    date_window = payload["date_window"]
    committee = {
        **metadata,
        "start_date": date_window.get("start_date"),
        "end_date": date_window.get("end_date"),
    }
    payload["committee"] = committee
    committee["description_html"] = render_markdown(committee.get("description_md"))
    committee["notes_html"] = render_markdown(committee.get("notes_md"))

    for event in payload["events"]:
        event["summary_html"] = render_markdown(event.get("summary_md"))
        event["minutes_html"] = render_markdown(event.get("minutes_md"))
        for contribution in event.get("contributions", []):
            contribution["minutes_html"] = render_markdown(
                contribution.get("minutes_md")
            )

    return payload


def _load_template_assets() -> tuple[str, str, Environment]:
    render_dir = Path(__file__).resolve().parent.parent / "render"
    css = (render_dir / "styles.css").read_text(encoding="utf-8")
    js = (render_dir / "app.js.j2").read_text(encoding="utf-8")
    env = Environment(
        loader=FileSystemLoader(str(render_dir)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return css, js, env


def _apply_date_override(
    history: ProjectFile, from_date: date | None, to_date: date | None
) -> ProjectFile:
    if from_date is None and to_date is None:
        return history

    window_start = from_date or history.date_window.start_date
    window_end = to_date if to_date is not None else history.date_window.end_date
    filtered_events = [
        event
        for event in history.events
        if event.date >= window_start
        and (window_end is None or event.date <= window_end)
    ]

    return history.model_copy(
        update={
            "date_window": DateWindow(start_date=window_start, end_date=window_end),
            "events": filtered_events,
        }
    )


def build_html(
    input_yaml: Path,
    output_path: Path | None,
    overwrite: bool = False,
    from_date: date | None = None,
    to_date: date | None = None,
) -> Path:
    """Build a standalone HTML file from the YAML input."""
    result = validate_yaml(input_yaml)
    history = _apply_date_override(result.history, from_date=from_date, to_date=to_date)
    history = normalize_history(history)
    payload = _render_payload(history)

    target = output_path if output_path is not None else default_output_html(input_yaml)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Output file exists: {target} (use --overwrite)")

    css, js, env = _load_template_assets()
    template = env.get_template("template.html.j2")

    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = template.render(
        page_title=payload["metadata"]["name"],
        css=css,
        app_js=js,
        data_json=data_json,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target
