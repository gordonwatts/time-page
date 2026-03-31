"""HTML output structure tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from committee_builder.indico.client import IndicoMeeting
from committee_builder.pipeline.build_pipeline import build_html

SAMPLE = """
schema_version: "1.0"
metadata:
  name: "Output Test"
  subtitle: "Subtitle"
  description_md: "A *desc*"
date_window:
  start_date: "2023-01-01"
  end_date: "2023-01-31"
event_type_styles:
  meeting: {label: "Meeting", color: "sky"}
  report: {label: "Report", color: "emerald"}
  decision: {label: "Decision", color: "rose"}
  milestone: {label: "Milestone", color: "amber"}
  external: {label: "External", color: "violet"}
events:
  - id: "evt-1"
    type: "meeting"
    title: "Kickoff"
    date: "2023-01-10"
    important: true
    summary_md: "# Heading"
    minutes_md: "## Minutes\n\n- Approved"
"""

MERGED_WITH_SOURCE = (
    SAMPLE
    + """
indico_category_sources:
  - name: "Analysis Model Group Meetings"
    category_id: 42
    base_url: "https://indico.example.com"
    color: "#ffd6d6"
"""
)


def test_output_contains_inlined_assets_and_data(tmp_path: Path) -> None:
    src = tmp_path / "source.yaml"
    src.write_text(SAMPLE, encoding="utf-8")

    out = build_html(src, output_path=None, overwrite=False)
    text = out.read_text(encoding="utf-8")

    assert "<style>" in text
    assert '<script id="committee-data" type="application/json">' in text
    assert "Output Test" in text
    assert "timeline-item" in text
    assert ".timeline-item:hover .timeline-content" in text
    assert ".timeline-content { min-width: 0; display: flex; flex-wrap: wrap; align-items: center;" in text
    assert ".title { min-width: 0; flex: 1 1 12rem; overflow-wrap: break-word; }" in text
    assert ".timeline-pills { min-width: 0; flex: 0 1 14rem; margin-left: auto; display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: center;" in text
    assert ".timeline-pills .pill" in text
    assert "display: inline-flex" in text
    assert "align-items: center" in text
    assert "justify-content: center" in text
    assert "max-width: min(100%, 14rem)" in text
    assert 'class="search-clear${showClearSearch ? "" : " hidden"}"' in text
    assert 'aria-label="Clear search"' in text
    assert '"minutes_html":' in text
    assert "Approved" in text


def test_output_renders_merged_local_and_imported_source_events(
    tmp_path: Path,
    monkeypatch,
) -> None:
    src = tmp_path / "source.yaml"
    src.write_text(MERGED_WITH_SOURCE, encoding="utf-8")

    def _fake_fetch_meetings(*_args: object, **_kwargs: object) -> list[IndicoMeeting]:
        return [
            IndicoMeeting(
                remote_id="1001",
                title="Imported Coordination",
                start_datetime=datetime(2023, 1, 12, 9, 30),
                description="Imported agenda",
                participants=["Jane Doe"],
                documents=[],
                contributions=[],
                url="https://indico.example.com/event/1001",
            )
        ]

    monkeypatch.setattr(
        "committee_builder.pipeline.build_pipeline.fetch_meetings",
        _fake_fetch_meetings,
    )

    out = build_html(src, output_path=None, overwrite=False)
    text = out.read_text(encoding="utf-8")

    assert "Kickoff" in text
    assert "Imported Coordination" in text
    assert '"source_name": "Analysis Model Group Meetings"' in text
    assert "#ffd6d6" in text


def test_output_does_not_escape_inline_script_and_json(tmp_path: Path) -> None:
    src = tmp_path / "source.yaml"
    src.write_text(SAMPLE, encoding="utf-8")

    out = build_html(src, output_path=None, overwrite=False)
    text = out.read_text(encoding="utf-8")

    assert "&#34;" not in text
    assert "(() => {" in text
    assert 'const root = document.getElementById("app");' in text
    assert 'searchClear?.addEventListener("click"' in text
