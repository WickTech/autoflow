"""LLM bounds: timeout, retries, token budget, and graceful degradation.

The openai package is optional, so these tests inject a fake module rather than
importing it — they run identically with or without the extra installed.
"""
from __future__ import annotations

import sys
import types

import pytest

from autoflow import llm

TEXT = (
    "The weather was mild. The new AI model set a record on the reasoning "
    "benchmark, and the AI model is open source. Lunch was fine."
)


class _FakeCompletions:
    def __init__(self, outcome, usage_tokens=42):
        self._outcome = outcome
        self._usage_tokens = usage_tokens
        self.kwargs: dict = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self._outcome, Exception):
            raise self._outcome
        message = types.SimpleNamespace(content=self._outcome)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=message)],
            usage=types.SimpleNamespace(total_tokens=self._usage_tokens),
        )


@pytest.fixture
def fake_openai(monkeypatch):
    """Install a stub `openai` module and return a handle on what it received."""
    captured: dict = {}

    def _make(outcome="A crisp summary.", usage_tokens=42):
        completions = _FakeCompletions(outcome, usage_tokens)

        class _FakeClient:
            def __init__(self, **kwargs):
                captured["client_kwargs"] = kwargs
                self.chat = types.SimpleNamespace(completions=completions)

        module = types.ModuleType("openai")
        module.OpenAI = _FakeClient
        monkeypatch.setitem(sys.modules, "openai", module)
        captured["completions"] = completions
        return captured

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    llm.reset_budget()
    yield _make
    llm.reset_budget()


def test_uses_extractive_summary_without_an_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm.summarize(TEXT, 1) == llm._extractive_summary(TEXT, 1)


def test_llm_summary_is_used_when_available(fake_openai):
    fake_openai()
    assert llm.summarize(TEXT, 1) == "A crisp summary."


def test_timeout_and_retries_are_passed_to_the_client(fake_openai, monkeypatch):
    monkeypatch.setenv("AUTOFLOW_LLM_TIMEOUT", "7.5")
    monkeypatch.setenv("AUTOFLOW_LLM_RETRIES", "1")
    monkeypatch.setenv("AUTOFLOW_LLM_MAX_TOKENS", "120")
    captured = fake_openai()

    llm.summarize(TEXT, 1)

    assert captured["client_kwargs"]["timeout"] == 7.5
    assert captured["client_kwargs"]["max_retries"] == 1
    assert captured["completions"].kwargs["max_tokens"] == 120


def test_malformed_env_falls_back_to_defaults(fake_openai, monkeypatch):
    monkeypatch.setenv("AUTOFLOW_LLM_TIMEOUT", "not-a-number")
    captured = fake_openai()
    llm.summarize(TEXT, 1)
    assert captured["client_kwargs"]["timeout"] == llm.DEFAULT_TIMEOUT


def test_api_failure_degrades_instead_of_raising(fake_openai):
    fake_openai(outcome=RuntimeError("API is down"))
    assert llm.summarize(TEXT, 1) == llm._extractive_summary(TEXT, 1)


def test_empty_llm_response_degrades(fake_openai):
    fake_openai(outcome="   ")
    assert llm.summarize(TEXT, 1) == llm._extractive_summary(TEXT, 1)


def test_token_usage_is_tracked(fake_openai):
    fake_openai(usage_tokens=30)
    llm.summarize(TEXT, 1)
    llm.summarize(TEXT, 1)
    assert llm.tokens_used() == 60


def test_budget_exhaustion_switches_to_extractive(fake_openai, monkeypatch):
    monkeypatch.setenv("AUTOFLOW_LLM_TOKEN_BUDGET", "50")
    fake_openai(usage_tokens=40)

    assert llm.summarize(TEXT, 1) == "A crisp summary."  # 40 used, under budget
    assert llm.summarize(TEXT, 1) == "A crisp summary."  # 80 used, budget now blown
    assert llm.summarize(TEXT, 1) == llm._extractive_summary(TEXT, 1)


def test_zero_budget_means_unlimited(fake_openai, monkeypatch):
    monkeypatch.setenv("AUTOFLOW_LLM_TOKEN_BUDGET", "0")
    fake_openai(usage_tokens=10_000)
    llm.summarize(TEXT, 1)
    assert llm.summarize(TEXT, 1) == "A crisp summary."


def test_reset_budget_clears_the_counter(fake_openai):
    fake_openai(usage_tokens=25)
    llm.summarize(TEXT, 1)
    assert llm.tokens_used() == 25
    llm.reset_budget()
    assert llm.tokens_used() == 0
