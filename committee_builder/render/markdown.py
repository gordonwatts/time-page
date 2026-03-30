"""Markdown rendering helpers."""

from __future__ import annotations

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin


def _link_open_new_tab(
    self: object,
    tokens: list,
    idx: int,
    options: object,
    env: object,
) -> str:
    """Render link_open tokens with target="_blank" and rel="noopener noreferrer"."""
    tokens[idx].attrSet("target", "_blank")
    tokens[idx].attrSet("rel", "noopener noreferrer")
    return self.renderToken(tokens, idx, options, env)  # type: ignore[attr-defined]


def _make_md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
    md.enable("table")
    md.use(dollarmath_plugin)
    md.add_render_rule("link_open", _link_open_new_tab)
    return md


_MD = _make_md()


def render_markdown(text: str | None) -> str:
    """Render markdown (with dollar-math) into HTML.

    Raw HTML input is disabled for archival safety.
    """
    if not text:
        return ""
    rendered = _MD.render(text)
    return (
        rendered.replace("&lt;br&gt;", "<br>")
        .replace("&lt;br/&gt;", "<br>")
        .replace("&lt;br /&gt;", "<br>")
    )
