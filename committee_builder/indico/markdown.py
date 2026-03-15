"""Helpers for converting Indico HTML snippets into Markdown."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin

from markdownify import markdownify as _markdownify


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    cleaned = (
        unescape(text).replace("\xa0", " ").replace("Â", "").replace("Ã‚", "")
    )
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _absolutize_html_urls(value: str, base_url: str | None) -> str:
    if not base_url:
        return value

    def replace(match: re.Match[str]) -> str:
        attr = match.group("attr")
        quote = match.group("quote")
        url = match.group("url").strip()
        if not url or re.match(r"^(?:[a-z][a-z0-9+.-]*:|#)", url, flags=re.IGNORECASE):
            return match.group(0)
        return f'{attr}={quote}{urljoin(base_url.rstrip("/") + "/", url)}{quote}'

    return re.sub(
        r'(?P<attr>href|src)=(?P<quote>["\'])(?P<url>.*?)(?P=quote)',
        replace,
        value,
        flags=re.IGNORECASE,
    )


def html_to_markdown(value: str | None, base_url: str | None = None) -> str:
    """Convert a small HTML fragment from Indico into Markdown."""
    if not value:
        return ""

    if "<" not in value and ">" not in value:
        return _normalize_text(value)

    value = _absolutize_html_urls(value, base_url=base_url)
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
