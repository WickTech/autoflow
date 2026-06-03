"""Summarization with a graceful offline fallback.

With OPENAI_API_KEY set, ``summarize`` calls the chat model. Without it, it uses
a deterministic frequency-based extractive summarizer — no network, fully
reproducible, perfect for CI and tests.
"""
from __future__ import annotations

import os
import re
from collections import Counter

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
    text = text.strip()
    if not text:
        return ""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _extractive_summary(text, max_sentences)

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL") or None)
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "Summarize the text in at most "
             f"{max_sentences} crisp sentences. No preamble."},
            {"role": "user", "content": text[:6000]},
        ],
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()
