"""Schema validation tests."""

from datetime import date

import pytest

from committee_builder.schema.models import CommitteeHistory
from committee_builder.schema.validators import (
    SemanticValidationError,
    validate_semantics,
)


def _base_doc() -> dict:
    return {
        "schema_version": "1.0",
        "committee": {
            "name": "Test Committee",
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


def test_schema_parses() -> None:
    history = CommitteeHistory.model_validate(_base_doc())
    assert history.committee.start_date == date(2023, 1, 1)
    assert len(history.events) == 1
    assert history.events[0].minutes_md == "Minutes"
    assert history.events[0].contributions[0].minutes_md == "Talk minutes"


def test_duplicate_event_id_fails_semantics() -> None:
    doc = _base_doc()
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
