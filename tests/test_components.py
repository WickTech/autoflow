from autoflow.llm import _extractive_summary
from autoflow.models import Item
from autoflow.processors.dedup import DedupProcessor
from autoflow.processors.keyword_filter import KeywordFilter


def test_extractive_summary_picks_salient_sentence():
    text = (
        "The weather was mild. The new AI model set a record on the reasoning "
        "benchmark, and the AI model is open source. Lunch was fine."
    )
    summary = _extractive_summary(text, max_sentences=1)
    assert "model" in summary.lower()


def test_keyword_filter_include_exclude():
    items = [
        Item(title="AI breakthrough", url="a", content="about llm agents"),
        Item(title="Sports update", url="b", content="football scores"),
        Item(title="AI gossip", url="c", content="rumor and ai drama"),
    ]
    kept = KeywordFilter(include=["ai"], exclude=["gossip"]).process(items)
    titles = {i.title for i in kept}
    assert titles == {"AI breakthrough"}


def test_dedup_within_batch():
    items = [
        Item(title="x", url="http://same"),
        Item(title="x again", url="http://same"),  # same URL → same fingerprint
        Item(title="y", url="http://other"),
    ]
    out = DedupProcessor(persist=False).process(items)
    assert len(out) == 2


def test_fingerprint_stable_for_same_url():
    a = Item(title="t1", url="http://x")
    b = Item(title="t2", url="http://x")
    assert a.fingerprint == b.fingerprint
