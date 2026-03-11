"""Path helper utilities."""

from __future__ import annotations

from pathlib import Path


def default_output_html(input_yaml: Path) -> Path:
    """Derive output path from input by replacing extension with .html."""
    return input_yaml.with_suffix(".html")
