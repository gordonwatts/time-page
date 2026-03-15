"""Markdown rendering tests."""

from committee_builder.render.markdown import render_markdown


def test_markdown_and_math_render() -> None:
    html = render_markdown("# Title\n\nInline math: $E=mc^2$")
    assert "<h1>Title</h1>" in html
    assert "math" in html or "E=mc^2" in html


def test_raw_html_is_not_rendered() -> None:
    html = render_markdown("<script>alert('x')</script>")
    assert "<script>" not in html


def test_markdown_tables_render() -> None:
    html = render_markdown(
        "| Talk | Authors |\n| --- | --- |\n| Introduction | Jane Doe |"
    )
    assert "<table>" in html
    assert "<td>Introduction</td>" in html


def test_markdown_allows_br_tags_in_generated_content() -> None:
    html = render_markdown("| Documents |\n| --- |\n| one<br>two |")
    assert "one<br>two" in html


def test_markdown_renders_inline_images() -> None:
    html = render_markdown("![plot](https://indico.cern.ch/event/1/attachments/2/3/plot.png)")
    assert '<img src="https://indico.cern.ch/event/1/attachments/2/3/plot.png"' in html
