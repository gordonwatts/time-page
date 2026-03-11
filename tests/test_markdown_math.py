"""Markdown rendering tests."""

from committee_builder.render.markdown import render_markdown


def test_markdown_and_math_render() -> None:
    html = render_markdown("# Title\n\nInline math: $E=mc^2$")
    assert "<h1>Title</h1>" in html
    assert "math" in html or "E=mc^2" in html


def test_raw_html_is_not_rendered() -> None:
    html = render_markdown("<script>alert('x')</script>")
    assert "<script>" not in html
