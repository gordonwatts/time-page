"""Build pipeline for standalone HTML generation."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from committee_builder.io.normalize import normalize_history
from committee_builder.io.paths import default_output_html
from committee_builder.pipeline.validate_pipeline import validate_yaml
from committee_builder.render.markdown import render_markdown


def _render_payload(history) -> dict:
    payload = history.model_dump(mode="json")
    committee = payload["committee"]
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


def build_html(
    input_yaml: Path, output_path: Path | None, overwrite: bool = False
) -> Path:
    """Build a standalone HTML file from the YAML input."""
    result = validate_yaml(input_yaml)
    history = normalize_history(result.history)
    payload = _render_payload(history)

    target = output_path if output_path is not None else default_output_html(input_yaml)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Output file exists: {target} (use --overwrite)")

    css, js, env = _load_template_assets()
    template = env.get_template("template.html.j2")

    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = template.render(
        page_title=payload["committee"]["name"],
        css=css,
        app_js=js,
        data_json=data_json,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target
