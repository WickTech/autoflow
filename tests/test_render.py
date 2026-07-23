"""Shared rendering: markup dialects, escaping, and message chunking."""
from __future__ import annotations

import pytest

from autoflow import render
from autoflow.models import Item

ITEM = Item(title="AI model shipped", url="https://x.test/1", summary="It shipped.")


def test_slack_style_uses_pipe_links():
    out = render.render_text([ITEM], style="slack")
    assert "<https://x.test/1|AI model shipped>" in out


def test_markdown_style_uses_bracket_links():
    out = render.render_text([ITEM], style="markdown")
    assert "[AI model shipped](https://x.test/1)" in out


def test_plain_style_has_no_markup():
    out = render.render_text([ITEM], style="plain")
    assert out == "• AI model shipped — https://x.test/1 — It shipped."


def test_html_style_escapes_user_content():
    nasty = Item(title="<script>alert(1)</script>", url="https://x.test/?a=1&b=2")
    out = render.render_text([nasty], style="html")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "&amp;b=2" in out


def test_header_is_first_line_when_given():
    out = render.render_text([ITEM], header="*Digest*", style="slack")
    assert out.splitlines()[0] == "*Digest*"


def test_no_header_means_no_blank_first_line():
    assert render.render_text([ITEM], style="plain").startswith("•")


def test_items_without_urls_still_render():
    out = render.render_text([Item(title="No link", url="")], style="markdown")
    assert out == "• No link"


def test_unknown_style_raises():
    with pytest.raises(ValueError, match="unknown format"):
        render.render_text([ITEM], style="carrier-pigeon")


def test_html_document_escapes_and_reports_empty():
    assert "<em>No new items.</em>" in render.render_html_document([], title="D")
    doc = render.render_html_document([Item(title="a & b", url="")], title="T & T")
    assert "a &amp; b" in doc
    assert "T &amp; T" in doc


# --- chunking ---------------------------------------------------------------


def test_short_text_is_one_chunk():
    assert render.chunk("hello", 100) == ["hello"]


def test_empty_text_produces_no_chunks():
    assert render.chunk("", 100) == []


def test_chunks_split_on_line_boundaries():
    text = "\n".join(["aaaa"] * 10)  # 10 lines of 4 chars
    pieces = render.chunk(text, 14)
    assert all(len(piece) <= 14 for piece in pieces)
    # Nothing is lost and no line is broken mid-way.
    assert "\n".join(pieces).replace("\n", "") == text.replace("\n", "")
    assert all(line == "aaaa" for piece in pieces for line in piece.split("\n"))


def test_a_single_oversized_line_is_hard_split():
    pieces = render.chunk("x" * 25, 10)
    assert pieces == ["x" * 10, "x" * 10, "x" * 5]


def test_oversized_line_after_normal_lines_flushes_first():
    pieces = render.chunk("short\n" + "y" * 12, 10)
    assert pieces[0] == "short"
    assert all(len(piece) <= 10 for piece in pieces)
