"""Markdown rendering helpers."""

from __future__ import annotations

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin


def _make_md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
    md.use(dollarmath_plugin)
    return md


_MD = _make_md()


def render_markdown(text: str | None) -> str:
    """Render markdown (with dollar-math) into HTML.

    Raw HTML input is disabled for archival safety.
    """
    if not text:
        return ""
    return _MD.render(text)
