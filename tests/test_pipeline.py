from pathlib import Path

from autoflow.pipeline import PipelineConfig, run_pipeline

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample-feed.xml")


def _cfg(tmp_path, **overrides):
    base = {
        "name": "test",
        "source": {"type": "rss", "url": SAMPLE},
        "processors": [
            {"type": "keyword_filter", "include": ["ai", "llm", "agent", "model"]},
            {"type": "summarize", "max_sentences": 1},
        ],
        "sinks": [{"type": "markdown", "path": str(tmp_path / "out.md")}],
    }
    base.update(overrides)
    return PipelineConfig(**base)


def test_pipeline_filters_and_summarizes(tmp_path):
    result = run_pipeline(_cfg(tmp_path), verbose=False)
    # 3 items in feed, 2 are AI-related → bakery item filtered out
    assert result.fetched == 3
    assert result.emitted == 2
    for item in result.items:
        assert item.summary  # summarize ran offline
    assert (tmp_path / "out.md").exists()


def test_dedup_suppresses_second_run(tmp_path):
    state = str(tmp_path / "state.json")
    cfg = _cfg(
        tmp_path,
        processors=[{"type": "dedup", "state_path": state}],
    )
    first = run_pipeline(cfg, verbose=False)
    second = run_pipeline(cfg, verbose=False)
    assert first.emitted == 3
    assert second.emitted == 0  # everything already seen


def test_unknown_component_raises(tmp_path):
    cfg = _cfg(tmp_path, source={"type": "does-not-exist"})
    import pytest

    with pytest.raises(KeyError):
        run_pipeline(cfg, verbose=False)
