from pathlib import Path

import pytest

from autoflow.models import Item
from autoflow.pipeline import PipelineConfig, run_pipeline
from autoflow.registry import sink
from autoflow.sinks.base import Sink

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample-feed.xml")


@sink("_boom")
class _BoomSink(Sink):
    """Test-only sink that always fails, to prove delivery failures are safe."""

    def emit(self, items: list[Item]) -> None:
        raise RuntimeError("delivery failed")


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
    with pytest.raises(KeyError):
        run_pipeline(cfg, verbose=False)


def test_dedup_state_not_persisted_when_a_sink_fails(tmp_path):
    """A failed delivery must not mark items as seen — the next run retries them."""
    state = tmp_path / "state.json"
    cfg = _cfg(
        tmp_path,
        processors=[{"type": "dedup", "state_path": str(state)}],
        sinks=[{"type": "_boom"}],
    )
    with pytest.raises(RuntimeError):
        run_pipeline(cfg, verbose=False)
    assert not state.exists()

    # Same items are still deliverable on the retry.
    cfg.sinks = [{"type": "markdown", "path": str(tmp_path / "out.md")}]
    assert run_pipeline(cfg, verbose=False).emitted == 3
    assert state.exists()
