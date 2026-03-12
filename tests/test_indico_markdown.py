"""Tests for Indico HTML to Markdown conversion."""

from committee_builder.indico.markdown import html_to_markdown


def test_html_to_markdown_converts_basic_markup() -> None:
    rendered = html_to_markdown(
        "<p>Hello <strong>team</strong>.</p>"
        "<p>Agenda:</p>"
        "<ul><li>Updates</li><li><em>Risks</em></li></ul>"
        '<p><a href="https://example.com">Slides</a></p>'
    )

    assert rendered == (
        "Hello **team**.\n\n"
        "Agenda:\n\n"
        "- Updates\n"
        "- *Risks*\n\n"
        "[Slides](https://example.com)"
    )


def test_html_to_markdown_normalizes_nbsp_noise() -> None:
    assert html_to_markdown("<p>Bio:&nbsp;</p><p>Â </p>") == "Bio:"
