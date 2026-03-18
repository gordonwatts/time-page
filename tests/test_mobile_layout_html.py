"""Tests for responsive stacked timeline layout in generated HTML."""

from pathlib import Path

from committee_builder.pipeline.build_pipeline import build_html


SAMPLE = """
schema_version: "1.0"
committee:
  name: "Responsive Layout Test"
  start_date: "2023-01-01"
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


def test_output_includes_mobile_timeline_first_layout(tmp_path: Path) -> None:
    src = tmp_path / "source.yaml"
    src.write_text(SAMPLE, encoding="utf-8")

    out = build_html(src, output_path=None, overwrite=False)
    text = out.read_text(encoding="utf-8")

    assert 'grid-template-areas:' in text
    assert '"timeline"' in text
    assert '.timeline {' in text
    assert 'max-height: min(24rem, 46vh);' in text
