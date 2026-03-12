"""Helpers for converting Indico HTML snippets into Markdown."""

from __future__ import annotations

import re
from html import unescape

from markdownify import markdownify as _markdownify


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    cleaned = (
        unescape(text).replace("\xa0", " ").replace("Â", "").replace("Ã‚", "")
    )
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def html_to_markdown(value: str | None) -> str:
    """Convert a small HTML fragment from Indico into Markdown."""
    if not value:
        return ""

    if "<" not in value and ">" not in value:
        return _normalize_text(value)

    rendered = _markdownify(
        value,
        heading_style="atx",
        bullets="-",
        strong_em_symbol="*",
    )
    rendered = rendered.replace("\xa0", " ").replace("Â", "").replace("Ã‚", "")
    rendered = re.sub(r"[ \t]+\n", "\n", rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()
