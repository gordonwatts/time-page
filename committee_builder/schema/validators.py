"""Semantic validation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from committee_builder.schema.models import ProjectFile


@dataclass
class ValidationResult:
    warnings: list[str]


class SemanticValidationError(ValueError):
    """Raised when semantic checks fail."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_semantics(project: ProjectFile) -> ValidationResult:
    """Validate semantic rules that go beyond type/schema checks."""
    errors: list[str] = []
    warnings: list[str] = []

    ids: set[str] = set()
    for event in project.events:
        if event.id in ids:
            errors.append(f"Duplicate event id: {event.id}")
        ids.add(event.id)

        if event.date < project.date_window.start_date:
            warnings.append(
                f"Event {event.id} date {event.date.isoformat()} is before date_window.start_date "
                f"{project.date_window.start_date.isoformat()}"
            )

        if project.date_window.end_date and event.date > project.date_window.end_date:
            warnings.append(
                f"Event {event.id} date {event.date.isoformat()} is after date_window.end_date "
                f"{project.date_window.end_date.isoformat()}"
            )

    if (
        project.date_window.end_date
        and project.date_window.end_date < project.date_window.start_date
    ):
        errors.append("date_window.end_date cannot be before date_window.start_date")

    if errors:
        raise SemanticValidationError(errors)

    return ValidationResult(warnings=warnings)
