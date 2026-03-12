"""Validation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from committee_builder.io.yaml_io import read_yaml
from committee_builder.schema.models import CommitteeHistory
from committee_builder.schema.validators import (
    SemanticValidationError,
    validate_semantics,
)


@dataclass
class PipelineValidationResult:
    history: CommitteeHistory
    warnings: list[str]


def validate_yaml(input_yaml: Path) -> PipelineValidationResult:
    """Load and validate a YAML committee source file."""
    raw = read_yaml(input_yaml)

    try:
        history = CommitteeHistory.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    try:
        semantic = validate_semantics(history)
    except SemanticValidationError as exc:
        raise ValueError(f"Semantic validation failed: {exc}") from exc

    return PipelineValidationResult(history=history, warnings=semantic.warnings)
