# ⚙️ autoflow

> A **pluggable content-automation pipeline**. Pull from sources, transform with LLMs, push to sinks — all described in a tiny YAML file and runnable on a schedule via GitHub Actions.

[![CI](https://github.com/WickTech/autoflow/actions/workflows/ci.yml/badge.svg)](https://github.com/WickTech/autoflow/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

`scrape → filter → dedup → summarize → publish`, configured declaratively.
Point it at any RSS/Atom feed and it'll build you a daily AI-news digest,
post it to Slack, and never repeat a story — without you writing glue code.

> 🔌 **Runs offline.** No API key? autoflow uses a deterministic extractive
> summarizer, so the whole pipeline (and CI) runs with zero secrets. Add
> `OPENAI_API_KEY` for LLM-quality summaries.

---

## ✅ Current Status

| | |
|---|---|
| **Tests** | 9/9 passing — pipeline, components, RSS parsing (all offline) |
| **CI** | GitHub Actions: lint (ruff) → pytest → live pipeline run on every push |
| **Scheduled digest** | `digest.yml` runs weekday mornings at 08:00 UTC, commits output, posts to webhook |
| **Python** | 3.10 and 3.12 tested |
| **Deployment** | `Dockerfile` ready; runs as a container or via `autoflow run` CLI |

---

## ✨ Why it's nice

- **Declarative pipelines** — a run is fully described by one YAML file.
- **Plugin architecture** — add a source/processor/sink with one decorator; the registry wires it in. No edits to the runner.
- **Stateful dedup** — fingerprints persist across runs, so scheduled jobs never re-post.
- **Batteries included** — RSS/Atom source; keyword-filter, dedup, summarize processors; console, Markdown, and webhook (Slack/Discord) sinks.
- **Ships scheduled** — a ready-to-use GitHub Action runs it weekday mornings and commits the digest.

---

## 🏗️ Architecture

```mermaid
flowchart LR
    subgraph Pipeline (declared in YAML)
        S[Source<br/>rss] --> P1[keyword_filter] --> P2[dedup] --> P3[summarize]
        P3 --> K1[console]
        P3 --> K2[markdown]
        P3 --> K3[webhook]
    end
    REG[(Plugin registry)] -.resolves by name.-> S & P1 & P2 & P3 & K1 & K2 & K3
    ST[(Seen-state JSON)] <-->|dedup across runs| P2
```

```
autoflow/
├── models.py        Item (with stable fingerprint)
├── registry.py      @source / @processor / @sink decorators
├── pipeline.py      builds + runs a pipeline from config
├── llm.py           summarizer (LLM + offline extractive fallback)
├── state.py         persistent seen-set for dedup
├── sources/         rss.py
├── processors/      keyword_filter.py · dedup.py · summarize.py
└── sinks/           console.py · markdown.py · webhook.py
```

---

## 🚀 Quick start

```bash
git clone https://github.com/WickTech/autoflow && cd autoflow
pip install -e ".[dev]"

# Fully offline demo (reads a bundled sample feed)
autoflow run examples/offline-demo.yaml

# See everything that's registered
autoflow plugins

# Check a config without running it (typos, unknown plugins, unset ${ENV_VARS})
autoflow validate examples/tech-digest.yaml
```

A pipeline is just YAML:

```yaml
name: tech-digest
source:
  type: rss
  urls: [https://hnrss.org/frontpage]
  limit: 30
processors:
  # Word-boundary matching: "ai" hits "AI model", not "chair".
  # Add `substring: true` for loose matching.
  - { type: keyword_filter, include: [ai, llm, agent] }
  - { type: dedup }
  - { type: summarize, max_sentences: 2 }
sinks:
  - { type: markdown, path: out/tech-digest.md, title: "AI Tech Digest" }
  - { type: webhook, url: ${AUTOFLOW_WEBHOOK_URL}, header: "*🤖 Today's AI reads*" }
```

```bash
autoflow run examples/tech-digest.yaml
```

---

## ⏰ Run it on a schedule

[`.github/workflows/digest.yml`](.github/workflows/digest.yml) runs the pipeline
every weekday at 08:00 UTC, commits the generated Markdown, and posts to a
webhook. Add `OPENAI_API_KEY` and `AUTOFLOW_WEBHOOK_URL` as repo secrets to turn
on LLM summaries and Slack/Discord delivery. That's a self-updating newsletter
with no server to run.

---

## 🧩 Extending it

```python
from autoflow.registry import sink
from autoflow.sinks.base import Sink

@sink("email")           # now usable as `type: email` in any pipeline YAML
class EmailSink(Sink):
    def emit(self, items):
        ...
```

---

## 🧪 Testing

```bash
pytest -q          # pipeline, components, and RSS parsing — all offline
ruff check .
```

CI runs the suite on Python 3.10 & 3.12 and executes a real pipeline run on
every push.

---

## 🗺️ Roadmap

Features planned for future iterations:

- [ ] **Web scraper source** — Playwright-based source for JS-rendered pages (Hacker News, Reddit, X/Twitter)
- [ ] **Reddit source** — pull top posts from any subreddit via the JSON API
- [ ] **Email sink (SMTP)** — send digests as HTML emails via configurable SMTP
- [ ] **Telegram sink** — post to a Telegram channel via Bot API
- [ ] **GitHub Issues sink** — open labelled issues for each item (useful for bug/PR digests)
- [ ] **Pipeline DAG** — fanout/merge support so one source can feed multiple independent processor chains
- [ ] **SQLite state backend** — replace JSON seen-state with SQLite for concurrent-safe dedup
- [ ] **Retry + dead-letter queue** — exponential backoff on source fetch failures; failed items go to a DLQ file
- [ ] **Error reporting webhook** — post pipeline failure summaries to a separate Slack channel
- [ ] **Schedule builder** — interactive CLI wizard to generate `digest.yml` from prompts
- [ ] **Notion source** — pull pages from a Notion database via the Notion API
- [ ] **Content scoring** — rank items by LLM-judged relevance before filtering, not just keyword match

---

## 📈 What this demonstrates

- Designing a small **extensible framework** (registry + plugin interfaces), not just a script.
- Idempotent, **stateful automation** safe to run on a schedule.
- Practical LLM integration with a reproducible offline fallback.
- End-to-end automation delivery via GitHub Actions.

## 📄 License

MIT — see [LICENSE](./LICENSE).
