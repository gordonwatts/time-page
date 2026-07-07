"""Build pipeline orchestration tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from committee_builder.indico.client import (
    IndicoContribution,
    IndicoDocument,
    IndicoMeeting,
)
from committee_builder.pipeline.build_pipeline import build_html


def test_build_fetches_transforms_and_merges_sources(
    tmp_path: Path, monkeypatch
) -> None:
    source_yaml = tmp_path / "project.yaml"
    source_yaml.write_text(
        """
schema_version: "1.0"
metadata:
  name: "Pipeline Test"
date_window:
  start_date: "2025-01-01"
  end_date: "2025-01-31"
event_type_styles:
  meeting: {label: "Meeting", color: "sky"}
  report: {label: "Report", color: "emerald"}
  decision: {label: "Decision", color: "rose"}
  milestone: {label: "Milestone", color: "amber"}
  external: {label: "External", color: "violet"}
events:
  - id: "CERN-101"
    type: "meeting"
    title: "Local override title"
    date: "2025-01-15"
    summary_md: "Keep me."
indico_category_sources:
  - name: "CERN"
    category_id: 11
    base_url: "https://indico.example.com"
    color: "#f3d9f2"
    title_matches: ["Weekly"]
    title_exclude_patterns: ["Skip"]
""",
        encoding="utf-8",
    )

    def _fake_fetch_meetings(*_args, **_kwargs) -> list[IndicoMeeting]:
        return [
            IndicoMeeting(
                remote_id="101",
                title="Weekly Physics",
                start_datetime=datetime(2025, 1, 10, 9, 0, 0),
                description="<p>Agenda body</p>",
                participants=["Alice"],
                documents=[],
                url="https://indico.example.com/event/101",
                minutes="<p>Minutes body</p>",
                contributions=[
                    IndicoContribution(
                        title="Detector update",
                        speaker_names=["Bob"],
                        documents=[
                            IndicoDocument(
                                label="slides.pdf",
                                url="https://indico.example.com/files/slides.pdf",
                            )
                        ],
                        minutes="<p>Talk minutes</p>",
                    )
                ],
            ),
            IndicoMeeting(
                remote_id="102",
                title="Skip me",
                start_datetime=datetime(2025, 1, 10, 9, 0, 0),
                description="<p>Should not pass filters</p>",
                participants=[],
                documents=[],
                url="https://indico.example.com/event/102",
            ),
            IndicoMeeting(
                remote_id="103",
                title="Weekly Operations",
                start_datetime=datetime(2025, 1, 11, 9, 0, 0),
                description="<p>Included meeting</p>",
                participants=["Charlie"],
                documents=[],
                url="https://indico.example.com/event/103",
                contributions=[
                    IndicoContribution(
                        title="Operations report",
                        documents=[
                            IndicoDocument(
                                label="ops.pdf",
                                url="https://indico.example.com/files/ops.pdf",
                            )
                        ],
                        minutes="<p>Talk minutes</p>",
                    ),
                    IndicoContribution(
                        title="Detector status",
                        documents=[
                            IndicoDocument(
                                label="detector.pdf",
                                url="https://indico.example.com/files/detector.pdf",
                            )
                        ],
                    ),
                    IndicoContribution(
                        title="Software update",
                        documents=[
                            IndicoDocument(
                                label="software.pdf",
                                url="https://indico.example.com/files/software.pdf",
                            )
                        ],
                    ),
                    IndicoContribution(
                        title="DAQ review",
                        documents=[
                            IndicoDocument(
                                label="daq.pdf",
                                url="https://indico.example.com/files/daq.pdf",
                            )
                        ],
                    ),
                    IndicoContribution(
                        title="Physics outlook",
                        documents=[
                            IndicoDocument(
                                label="physics.pdf",
                                url="https://indico.example.com/files/physics.pdf",
                            )
                        ],
                    ),
                    IndicoContribution(
                        title="Scheduling",
                        documents=[
                            IndicoDocument(
                                label="schedule.pdf",
                                url="https://indico.example.com/files/schedule.pdf",
                            )
                        ],
                    ),
                ],
            ),
        ]

    monkeypatch.setattr(
        "committee_builder.pipeline.build_pipeline.fetch_meetings",
        _fake_fetch_meetings,
    )

    output = build_html(source_yaml, output_path=None, overwrite=False)
    rendered = output.read_text(encoding="utf-8")

    # Imported meeting with duplicate ID should not replace the local event.
    assert "Local override title" in rendered
    assert "Weekly Physics" not in rendered
    # Excluded title pattern should remove this imported event.
    assert "Skip me" not in rendered
    # Imported markdown conversion should be represented in serialized payload.
    assert "Talk minutes" in rendered
    # Timeline short label should list up to five document-backed talk titles and then indicate truncation.
    assert (
        '"short_label": "Operations report, Detector status, Software update, '
        'DAQ review, Physics outlook, ..."' in rendered
    )
    # Source attribution should carry through for imported events.
    assert '"source_name": "CERN"' in rendered


def test_build_fetches_event_source_and_honors_range(
        tmp_path: Path, monkeypatch
) -> None:
        source_yaml = tmp_path / "project.yaml"
        source_yaml.write_text(
                """
schema_version: "1.0"
metadata:
    name: "Pipeline Event Source Test"
date_window:
    start_date: "2025-01-01"
    end_date: "2025-01-31"
event_type_styles:
    meeting: {label: "Meeting", color: "sky"}
    report: {label: "Report", color: "emerald"}
    decision: {label: "Decision", color: "rose"}
    milestone: {label: "Milestone", color: "amber"}
    external: {label: "External", color: "violet"}
events: []
indico_category_sources:
    - name: "ATLAS Study Group"
      source_type: "event"
      event_id: "99"
      base_url: "https://indico.example.com"
      color: "#f3d9f2"
""",
                encoding="utf-8",
        )

        def _fake_fetch_event_meeting(*_args, **_kwargs) -> IndicoMeeting:
                return IndicoMeeting(
                        remote_id="99",
                        title="ATLAS Study Group",
                        start_datetime=datetime(2025, 1, 20, 9, 0, 0),
                        description="<p>Study group meeting</p>",
                        participants=["Alice"],
                        documents=[],
                        url="https://indico.example.com/event/99",
                )

        monkeypatch.setattr(
                "committee_builder.pipeline.build_pipeline.fetch_event_meeting",
                _fake_fetch_event_meeting,
        )

        output = build_html(source_yaml, output_path=None, overwrite=False)
        rendered = output.read_text(encoding="utf-8")
        assert '"id": "ATLAS Study Group-99"' in rendered
        assert "Study group meeting" in rendered

        # Same event source should be excluded when outside the effective range.
        source_yaml.write_text(
                source_yaml.read_text(encoding="utf-8").replace(
                        "end_date: \"2025-01-31\"",
                        "end_date: \"2025-01-10\"",
                ),
                encoding="utf-8",
        )
        output = build_html(source_yaml, output_path=output, overwrite=True)
        rendered = output.read_text(encoding="utf-8")
        assert '"id": "ATLAS Study Group-99"' not in rendered
        assert "Study group meeting" not in rendered
