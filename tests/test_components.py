import json

from autoflow.llm import _extractive_summary
from autoflow.models import Item
from autoflow.processors.dedup import DedupProcessor
from autoflow.processors.keyword_filter import KeywordFilter
from autoflow.state import SeenStore


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


def test_keyword_filter_respects_word_boundaries():
    """'ai' must not match 'chair', 'said', or 'Ukraine'."""
    items = [
        Item(title="Ergonomic chair review", url="a", content="the chair said hello"),
        Item(title="Ukraine update", url="b", content="certain developments"),
        Item(title="AI model shipped", url="c", content="a new model"),
    ]
    kept = KeywordFilter(include=["ai"]).process(items)
    assert [i.title for i in kept] == ["AI model shipped"]


def test_keyword_filter_substring_mode_is_opt_in():
    items = [Item(title="Ergonomic chair", url="a", content="")]
    assert KeywordFilter(include=["ai"]).process(items) == []
    assert len(KeywordFilter(include=["ai"], substring=True).process(items)) == 1


def test_keyword_filter_matches_multi_word_phrases():
    items = [
        Item(title="Machine   learning at scale", url="a", content=""),
        Item(title="Learning machine embroidery", url="b", content=""),
    ]
    kept = KeywordFilter(include=["machine learning"]).process(items)
    assert [i.title for i in kept] == ["Machine   learning at scale"]


def test_seen_store_roundtrips_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "state.json"
    store = SeenStore(path)
    store.add("abc")
    store.add("def")
    store.save()

    assert json.loads(path.read_text(encoding="utf-8")) == ["abc", "def"]
    assert "abc" in SeenStore(path)
    # The atomic write must not leave scratch files behind.
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_seen_store_survives_a_corrupt_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    store = SeenStore(path)
    assert "anything" not in store
    store.add("x")
    store.save()
    assert json.loads(path.read_text(encoding="utf-8")) == ["x"]
