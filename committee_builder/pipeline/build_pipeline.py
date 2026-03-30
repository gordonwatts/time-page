"""Build pipeline for standalone HTML generation."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from committee_builder.indico.client import (
    IndicoAuthError,
    IndicoContribution,
    IndicoDocument,
    IndicoMeeting,
    fetch_meetings,
)
from committee_builder.indico.markdown import html_to_markdown
from committee_builder.io.normalize import normalize_history
from committee_builder.io.paths import default_output_html
from committee_builder.pipeline.validate_pipeline import validate_yaml
from committee_builder.render.markdown import render_markdown
from committee_builder.schema.models import (
    CommitteeEvent,
    ContributionRef,
    DateWindow,
    DocumentRef,
    EventType,
    ProjectFile,
)

logger = logging.getLogger(__name__)

DEFAULT_API_KEY_ENV = "INDICO_API_KEY"
DEFAULT_API_TOKEN_ENV = "INDICO_API_TOKEN"


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


def _meeting_matches_title_patterns(title: str, title_patterns: list[str]) -> bool:
    if not title_patterns:
        return True
    return any(
        re.search(pattern, title, flags=re.IGNORECASE) for pattern in title_patterns
    )


def _meeting_matches_title_exclusions(title: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in patterns)


def _contributions_with_documents(
    contributions: list[IndicoContribution],
) -> list[IndicoContribution]:
    return [contribution for contribution in contributions if contribution.documents]


def _meeting_short_label(contributions: list[IndicoContribution]) -> str | None:
    titles: list[str] = []
    seen: set[str] = set()
    for contribution in _contributions_with_documents(contributions):
        title = contribution.title.strip()
        if not title:
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        titles.append(title)
    return ", ".join(titles) or None


def _build_document_ref(document: IndicoDocument) -> DocumentRef:
    return DocumentRef(
        label=document.label,
        url=document.url,
        talk_title=document.talk_title,
        speaker_names=document.speaker_names,
    )


def _build_contribution_ref(
    contribution: IndicoContribution, *, base_url: str
) -> ContributionRef:
    return ContributionRef(
        title=contribution.title,
        speaker_names=contribution.speaker_names,
        documents=[
            _build_document_ref(document) for document in contribution.documents
        ],
        minutes_md=html_to_markdown(contribution.minutes, base_url=base_url) or None,
    )


def _build_meeting_summary_md(meeting: IndicoMeeting, *, base_url: str) -> str:
    summary_md = html_to_markdown(meeting.description, base_url=base_url) or ""
    if meeting.url:
        indico_link = f"[Link To Indico]({meeting.url})"
        summary_md = (
            f"{indico_link}\n\n{summary_md.lstrip()}"
            if summary_md.strip()
            else indico_link
        )
    return summary_md


def _meeting_to_event(
    meeting: IndicoMeeting, *, source_name: str, source_color: str, base_url: str
) -> CommitteeEvent:
    interesting_contributions = _contributions_with_documents(meeting.contributions)
    is_interesting_meeting = bool(meeting.documents or interesting_contributions)

    return CommitteeEvent(
        id=f"{source_name}-{meeting.remote_id}",
        type=EventType.meeting,
        title=meeting.title,
        date=meeting.start_datetime.date(),
        important=is_interesting_meeting,
        short_label=_meeting_short_label(meeting.contributions),
        summary_md=_build_meeting_summary_md(meeting, base_url=base_url)
        or f"Imported from source `{source_name}`.",
        minutes_md=html_to_markdown(meeting.minutes, base_url=base_url) or None,
        participants=meeting.participants,
        tags=[],
        documents=[_build_document_ref(document) for document in meeting.documents],
        contributions=[
            _build_contribution_ref(contribution, base_url=base_url)
            for contribution in meeting.contributions
        ],
        source_name=source_name,
        source_color=source_color,
    )


def _fetch_source_events(
    history: ProjectFile,
    *,
    range_start: date,
    range_end: date,
) -> list[CommitteeEvent]:
    source_events: list[CommitteeEvent] = []
    for source in history.indico_category_sources:
        try:
            meetings = fetch_meetings(
                source,
                range_start,
                range_end,
                api_key_env=DEFAULT_API_KEY_ENV,
                api_token_env=DEFAULT_API_TOKEN_ENV,
            )
        except IndicoAuthError as exc:
            logger.warning("Skipping source '%s': %s", source.name, exc)
            continue

        for meeting in meetings:
            if not _meeting_matches_title_patterns(meeting.title, source.title_matches):
                continue
            if _meeting_matches_title_exclusions(
                meeting.title, source.title_exclude_patterns
            ):
                continue
            source_events.append(
                _meeting_to_event(
                    meeting,
                    source_name=source.name,
                    source_color=source.color,
                    base_url=source.base_url,
                )
            )
    return source_events


def _merge_events(
    local_events: list[CommitteeEvent],
    source_events: list[CommitteeEvent],
) -> list[CommitteeEvent]:
    # Duplicate strategy: local YAML events win over imported source events when IDs match.
    merged_by_id: dict[str, CommitteeEvent] = {
        event.id: event for event in source_events
    }
    for event in local_events:
        if event.id in merged_by_id:
            logger.warning(
                "Keeping local event for duplicate id '%s'; skipping imported record.",
                event.id,
            )
        merged_by_id[event.id] = event
    return list(merged_by_id.values())


def _orchestrate_history(
    history: ProjectFile, from_date: date | None, to_date: date | None
) -> ProjectFile:
    overridden_history = _apply_date_override(
        history,
        from_date=from_date,
        to_date=to_date,
    )
    range_start = overridden_history.date_window.start_date
    range_end = overridden_history.date_window.end_date or range_start

    fetched_events = _fetch_source_events(
        overridden_history,
        range_start=range_start,
        range_end=range_end,
    )
    merged_events = _merge_events(overridden_history.events, fetched_events)
    return overridden_history.model_copy(update={"events": merged_events})


def build_html(
    input_yaml: Path,
    output_path: Path | None,
    overwrite: bool = False,
    from_date: date | None = None,
    to_date: date | None = None,
) -> Path:
    """Build a standalone HTML file from the YAML input."""
    result = validate_yaml(input_yaml)
    history = _orchestrate_history(result.history, from_date=from_date, to_date=to_date)
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
