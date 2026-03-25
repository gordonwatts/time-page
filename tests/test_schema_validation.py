"""Schema validation tests."""

from datetime import date

import pytest

from committee_builder.schema.models import CommitteeHistory
from committee_builder.schema.validators import (
    SemanticValidationError,
    validate_semantics,
)


def _base_doc() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "metadata": {
            "name": "Test Committee",
            "subtitle": "Master model",
        },
        "date_window": {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        },
        "event_type_styles": {
            "meeting": {"label": "Meeting", "color": "sky"},
            "report": {"label": "Report", "color": "emerald"},
            "decision": {"label": "Decision", "color": "rose"},
            "milestone": {"label": "Milestone", "color": "amber"},
            "external": {"label": "External", "color": "violet"},
        },
        "events": [
            {
                "id": "evt-1",
                "type": "meeting",
                "title": "Kickoff",
                "date": "2023-01-12",
                "important": True,
                "summary_md": "Hello",
                "minutes_md": "Minutes",
                "contributions": [
                    {
                        "title": "Status",
                        "speaker_names": ["Jane Doe"],
                        "minutes_md": "Talk minutes",
                    }
                ],
            }
        ],
    }


def test_schema_parses_master_model_fields() -> None:
    history = CommitteeHistory.model_validate(_base_doc())
    assert history.metadata.name == "Test Committee"
    assert history.date_window.start_date == date(2023, 1, 1)
    assert len(history.events) == 1
    assert history.events[0].minutes_md == "Minutes"
    assert history.events[0].contributions[0].minutes_md == "Talk minutes"


def test_schema_migrates_legacy_committee_and_sources_fields() -> None:
    doc = {
        "schema_version": "1.0",
        "committee": {
            "name": "Legacy Committee",
            "subtitle": "Legacy subtitle",
            "start_date": "2023-01-01",
            "end_date": "2023-06-30",
        },
        "event_type_styles": {
            "meeting": {"label": "Meeting", "color": "sky"},
        },
        "events": [],
        "sources": [
            {
                "name": "CERN",
                "category_id": 11,
                "base_url": "https://indico.example.com",
                "color": "#abcdef",
            }
        ],
    }

    history = CommitteeHistory.model_validate(doc)
    assert history.metadata.name == "Legacy Committee"
    assert history.date_window.end_date == date(2023, 6, 30)
    assert history.indico_category_sources[0].name == "CERN"


def test_duplicate_event_id_fails_semantics() -> None:
    doc = _base_doc()
    assert isinstance(doc["events"], list)
    doc["events"].append(
        {
            "id": "evt-1",
            "type": "report",
            "title": "Dup",
            "date": "2023-03-01",
            "important": False,
            "summary_md": "Dup",
        }
    )
    history = CommitteeHistory.model_validate(doc)

    with pytest.raises(SemanticValidationError):
        validate_semantics(history)
