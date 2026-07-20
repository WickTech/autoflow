"""Summarization with a graceful offline fallback.

With OPENAI_API_KEY set, ``summarize`` calls the chat model. Without it, it uses
a deterministic frequency-based extractive summarizer — no network, fully
reproducible, perfect for CI and tests.

Every LLM call is bounded. A scheduled digest that hangs on a stuck API call
burns Actions minutes until the 6-hour job limit, and an unbounded token spend
is a bill waiting to happen. So calls carry a timeout and retry limit, the run
has an optional token budget, and *any* failure degrades to the extractive
summarizer rather than failing the pipeline — a slightly worse digest beats no
digest at all.
"""
from __future__ import annotations

import os
import re
from collections import Counter

from .log import log

DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 2
DEFAULT_MAX_TOKENS = 300

# Tokens consumed so far this process. Only enforced when a budget is set.
_tokens_used = 0


def reset_budget() -> None:
    """Reset the per-run token counter (called at the start of each pipeline run)."""
    global _tokens_used
    _tokens_used = 0


def tokens_used() -> int:
    return _tokens_used


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        log.warning("%s is not an integer, using %s", name, default)
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        log.warning("%s is not a number, using %s", name, default)
        return default

_SENT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-z']+")
_STOP = set(
    "the a an and or but if then of to in on at for with by is are was were be been "
    "this that these those it its as from has have had will would can could".split()
)


def _extractive_summary(text: str, max_sentences: int = 2) -> str:
    sentences = [s.strip() for s in _SENT_RE.split(text.strip()) if s.strip()]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    freq = Counter(w for w in _WORD_RE.findall(text.lower()) if w not in _STOP)
    if not freq:
        return " ".join(sentences[:max_sentences])

    def score(sentence: str) -> float:
        words = [w for w in _WORD_RE.findall(sentence.lower()) if w not in _STOP]
        return sum(freq[w] for w in words) / (len(words) or 1)

    ranked = sorted(range(len(sentences)), key=lambda i: score(sentences[i]), reverse=True)
    chosen = sorted(ranked[:max_sentences])  # keep original order
    return " ".join(sentences[i] for i in chosen)


def summarize(text: str, max_sentences: int = 2) -> str:
    global _tokens_used

    text = text.strip()
    if not text:
        return ""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _extractive_summary(text, max_sentences)

    budget = _env_int("AUTOFLOW_LLM_TOKEN_BUDGET", 0)  # 0 = unlimited
    if budget and _tokens_used >= budget:
        log.warning(
            "LLM token budget exhausted (%d/%d) — using extractive summaries for the rest",
            _tokens_used,
            budget,
        )
        return _extractive_summary(text, max_sentences)

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            timeout=_env_float("AUTOFLOW_LLM_TIMEOUT", DEFAULT_TIMEOUT),
            max_retries=_env_int("AUTOFLOW_LLM_RETRIES", DEFAULT_RETRIES),
        )
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Summarize the text in at most "
                 f"{max_sentences} crisp sentences. No preamble."},
                {"role": "user", "content": text[:6000]},
            ],
            temperature=0.3,
            max_tokens=_env_int("AUTOFLOW_LLM_MAX_TOKENS", DEFAULT_MAX_TOKENS),
        )
    except Exception as exc:  # noqa: BLE001 — any LLM failure degrades, never fails
        log.warning("LLM summarization failed (%s), falling back to extractive", exc)
        return _extractive_summary(text, max_sentences)

    usage = getattr(resp, "usage", None)
    if usage is not None:
        _tokens_used += int(getattr(usage, "total_tokens", 0) or 0)

    summary = (resp.choices[0].message.content or "").strip()
    return summary or _extractive_summary(text, max_sentences)
