"""HTML output structure tests."""

from pathlib import Path

from committee_builder.pipeline.build_pipeline import build_html

SAMPLE = """
schema_version: "1.0"
committee:
  name: "Output Test"
  subtitle: "Subtitle"
  description_md: "A *desc*"
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
    summary_md: "# Heading"
"""


def test_output_contains_inlined_assets_and_data(tmp_path: Path) -> None:
    src = tmp_path / "source.yaml"
    src.write_text(SAMPLE, encoding="utf-8")

    out = build_html(src, output_path=None, overwrite=False)
    text = out.read_text(encoding="utf-8")

    assert "<style>" in text
    assert '<script id="committee-data" type="application/json">' in text
    assert "Output Test" in text
    assert "timeline-item" in text
