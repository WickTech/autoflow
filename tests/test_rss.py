from pathlib import Path

import pytest

from autoflow.sources.rss import RssSource, html_to_text

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample-feed.xml")


def test_parses_rss_items_from_file():
    items = RssSource(url=SAMPLE).fetch()
    assert len(items) == 3
    first = items[0]
    assert first.title == "New open-source LLM beats benchmarks"
    assert first.url == "https://example.com/llm-news"
    assert "language model" in first.content


def test_limit_respected():
    items = RssSource(url=SAMPLE, limit=2).fetch()
    assert len(items) == 2


def test_entity_expansion_is_rejected(tmp_path):
    """Feeds are untrusted input — a 'billion laughs' bomb must not be expanded."""
    pytest.importorskip("defusedxml", reason="hardened parsing requires defusedxml")
    from defusedxml.common import EntitiesForbidden

    bomb = tmp_path / "bomb.xml"
    bomb.write_text(
        '<?xml version="1.0"?>\n'
        "<!DOCTYPE rss [\n"
        '  <!ENTITY a "aaaaaaaaaa">\n'
        '  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">\n'
        "]>\n"
        '<rss version="2.0"><channel><item>'
        "<title>&b;</title><link>http://x</link>"
        "</item></channel></rss>",
        encoding="utf-8",
    )
    with pytest.raises(EntitiesForbidden):
        RssSource(url=str(bomb)).fetch()


HNRSS_ITEM = """<?xml version="1.0"?>
<rss version="2.0"><channel><item>
<title>Show HN: Tom &amp;amp; Jerry</title>
<link>https://example.com/a</link>
<description><![CDATA[
<p>Article URL: <a href="https://example.com/a">https://example.com/a</a></p>
<p>Comments URL: <a href="https://news.ycombinator.com/item?id=1">https://news.ycombinator.com/item?id=1</a></p>
<p>Points: 22</p>
<p># Comments: 7</p>
]]></description>
</item></channel></rss>"""


def test_hnrss_metadata_is_not_treated_as_content(tmp_path):
    feed = tmp_path / "hn.xml"
    feed.write_text(HNRSS_ITEM, encoding="utf-8")
    (item,) = RssSource(url=str(feed)).fetch()
    assert item.content == ""
    assert "<" not in item.title and item.title == "Show HN: Tom & Jerry"
    assert item.metadata == {
        "comments_url": "https://news.ycombinator.com/item?id=1",
        "points": "22",
        "comments": "7",
    }


def test_html_descriptions_are_flattened_to_text():
    text = html_to_text(
        "<p>First &amp; <b>bold</b>.</p><script>alert(1)</script><p>Second\n  line.</p>"
    )
    assert text == "First & bold.\nSecond line."


def test_plain_text_passes_through_unchanged():
    assert html_to_text("  no markup here ") == "no markup here"
