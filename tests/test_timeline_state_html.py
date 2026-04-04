"""Tests for persisted timeline state wiring in generated HTML."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from committee_builder.indico.client import IndicoMeeting
from committee_builder.pipeline.build_pipeline import build_html


SAMPLE = """
schema_version: "1.0"
metadata:
  name: "Timeline State Test"
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
    summary_md: "Intro"
"""

MERGED_WITH_SOURCE = (
    SAMPLE
    + """
indico_category_sources:
  - name: "ATLAS"
    category_id: 77
    base_url: "https://indico.example.com"
    color: "#abcdef"
"""
)


def test_output_includes_timeline_state_persistence_hooks(tmp_path: Path) -> None:
    src = tmp_path / "source.yaml"
    src.write_text(SAMPLE, encoding="utf-8")

    out = build_html(src, output_path=None, overwrite=False)
    text = out.read_text(encoding="utf-8")

    assert "window.sessionStorage.getItem(storageKey)" in text
    assert "window.localStorage.getItem(seenStorageKey)" in text
    assert "timelineScrollTop: state.timelineScrollTop" in text
    assert "state.seenIds[eventId] = new Date().toISOString()" in text
    assert 'window.addEventListener("pagehide"' in text


def test_output_persists_state_with_merged_local_and_source_events(
    tmp_path: Path,
    monkeypatch,
) -> None:
    src = tmp_path / "source.yaml"
    src.write_text(MERGED_WITH_SOURCE, encoding="utf-8")

    def _fake_fetch_meetings(*_args: object, **_kwargs: object) -> list[IndicoMeeting]:
        return [
            IndicoMeeting(
                remote_id="1001",
                title="Imported Weekly",
                start_datetime=datetime(2023, 1, 20, 9, 0),
                description="desc",
                participants=[],
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

    assert '"Imported Weekly"' in text
    assert "selected.source_name" in text
    assert "selectedId: state.selectedId" in text
    assert 'class="seen-badge" aria-label="Seen">Seen</span>' in text
