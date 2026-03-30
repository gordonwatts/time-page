"""Path helper utilities."""

from __future__ import annotations

from pathlib import Path


def normalize_yaml_path(path: Path) -> Path:
    """Append .yaml when the provided config path has no suffix."""
    if path.suffix:
        return path
    return path.with_suffix(".yaml")


def default_output_html(input_yaml: Path) -> Path:
    """Derive output path from input by replacing extension with .html."""
    return input_yaml.with_suffix(".html")
