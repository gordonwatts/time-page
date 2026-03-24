"""Normalization helpers."""

from __future__ import annotations

from committee_builder.schema.models import ProjectFile


def normalize_history(history: ProjectFile) -> ProjectFile:
    """Return a copy with a stable event sort (date, then id)."""
    sorted_events = sorted(history.events, key=lambda e: (e.date, e.id))
    return history.model_copy(update={"events": sorted_events})
