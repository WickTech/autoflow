"""Config validation — catches bad YAML before a scheduled run does."""
from __future__ import annotations

from pathlib import Path

from autoflow.pipeline import PipelineConfig, validate_config

EXAMPLES = Path(__file__).parent.parent / "examples"
SAMPLE = str(EXAMPLES / "sample-feed.xml")


def _cfg(**over):
    base = {
        "name": "t",
        "source": {"type": "rss", "url": SAMPLE},
        "processors": [{"type": "keyword_filter", "include": ["ai"]}],
        "sinks": [{"type": "console"}],
    }
    base.update(over)
    return PipelineConfig(**base)


def _messages(issues, level):
    return [i.message for i in issues if i.level == level]


def test_valid_config_has_no_issues():
    assert validate_config(_cfg()) == []


def test_unknown_component_is_an_error():
    issues = validate_config(_cfg(source={"type": "nope"}))
    assert any("unknown source 'nope'" in m for m in _messages(issues, "error"))


def test_missing_type_is_an_error():
    issues = validate_config(_cfg(sinks=[{"path": "out.md"}]))
    assert any("missing required key 'type'" in m for m in _messages(issues, "error"))


def test_typo_in_key_is_a_warning():
    """The whole point: 'limt' used to be accepted silently."""
    issues = validate_config(_cfg(source={"type": "rss", "url": SAMPLE, "limt": 30}))
    assert any("does not use key 'limt'" in m for m in _messages(issues, "warning"))
    assert _messages(issues, "error") == []


def test_no_sinks_is_a_warning():
    issues = validate_config(_cfg(sinks=[]))
    assert any("no sinks configured" in m for m in _messages(issues, "warning"))


def test_unset_env_reference_is_a_warning(monkeypatch):
    monkeypatch.delenv("AUTOFLOW_WEBHOOK_URL", raising=False)
    issues = validate_config(
        _cfg(sinks=[{"type": "webhook", "url": "${AUTOFLOW_WEBHOOK_URL}"}])
    )
    assert any("which is unset" in m for m in _messages(issues, "warning"))


def test_set_env_reference_is_clean(monkeypatch):
    monkeypatch.setenv("AUTOFLOW_WEBHOOK_URL", "https://example.com/hook")
    issues = validate_config(
        _cfg(sinks=[{"type": "webhook", "url": "${AUTOFLOW_WEBHOOK_URL}"}])
    )
    assert issues == []


def test_reddit_requires_subreddits_only_at_runtime():
    """No required_keys declared, so validation stays quiet; fetch() still raises."""
    assert validate_config(_cfg(source={"type": "reddit", "subreddits": ["python"]})) == []


def test_shipped_examples_are_valid():
    """Every example must at least be error-free — CI runs the same check."""
    paths = sorted(EXAMPLES.glob("*.yaml"))
    assert paths, "no example configs found"
    for path in paths:
        issues = validate_config(PipelineConfig.from_yaml(str(path)))
        errors = [i for i in issues if i.level == "error"]
        assert errors == [], f"{path.name}: {errors}"
