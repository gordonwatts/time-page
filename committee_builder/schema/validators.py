"""Semantic validation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from committee_builder.schema.models import CommitteeHistory


@dataclass
class ValidationResult:
    warnings: list[str]


class SemanticValidationError(ValueError):
    """Raised when semantic checks fail."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_semantics(history: CommitteeHistory) -> ValidationResult:
    """Validate semantic rules that go beyond type/schema checks."""
    errors: list[str] = []
    warnings: list[str] = []

    ids: set[str] = set()
    for event in history.events:
        if event.id in ids:
            errors.append(f"Duplicate event id: {event.id}")
        ids.add(event.id)

        if event.date < history.committee.start_date:
            warnings.append(
                f"Event {event.id} date {event.date.isoformat()} is before committee start_date "
                f"{history.committee.start_date.isoformat()}"
            )

        if history.committee.end_date and event.date > history.committee.end_date:
            warnings.append(
                f"Event {event.id} date {event.date.isoformat()} is after committee end_date "
                f"{history.committee.end_date.isoformat()}"
            )

    if (
        history.committee.end_date
        and history.committee.end_date < history.committee.start_date
    ):
        errors.append("committee.end_date cannot be before committee.start_date")

    if errors:
        raise SemanticValidationError(errors)

    return ValidationResult(warnings=warnings)
