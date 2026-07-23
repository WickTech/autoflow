# autoflow — Roadmap

Ranked by **portfolio impact × implementation speed**. Effort: S ≤ half day,
M ≈ 1–2 days, L ≈ 3+ days.

---

## Now — stabilise (this week)

The pipeline has been dark for 3 weeks. Nothing new ships until it's provably green.

| # | Item | Effort | Status |
|---|------|--------|--------|
| 1 | Verify digest green via `workflow_dispatch`; commit the Reddit source | S | ⬜ **Yours** — needs git + Actions access |
| 2 | **Error-reporting webhook** — `if: failure()` step posting job + run URL | S | ✅ Done (`digest.yml`, `ci.yml`) |
| 3 | `autoflow validate <file>` — check YAML against plugin config specs | S | ✅ Done (`ConfigSpec`, `validate_config`, CLI) |
| 4 | Retry + backoff on source fetch | S | ✅ Done (`autoflow/net.py`, both sources) |
| 5 | Word-boundary `keyword_filter` (opt-in `substring: true`) | S | ✅ Done |
| 6 | `defusedxml` for RSS parsing + atomic `SeenStore.save()` | S | ✅ Done |

**Exit criteria:** two consecutive green scheduled runs, digest committed, webhook posted.
Only item 1 remains — everything else is in the working tree awaiting a test run and a push.

---

## Next — capability (2–4 weeks)

| # | Item | Effort | Status |
|---|------|--------|--------|
| 11 | Structured logging (`logging` + `--log-format json`) | S | ✅ Done (`autoflow/log.py`) |
| 12 | LLM timeout, retry, and per-run token budget | S | ✅ Done |
| — | Webhook delivery retries (audit follow-on) | S | ✅ Done (`net.post`) |
| 9 | SMTP email sink | S | ✅ Done (`sinks/email.py`, stdlib only) |
| 10 | Telegram sink | S | ✅ Done (`sinks/telegram.py`, with 4096-char chunking) |
| — | Webhook `format:` key (audit #12) | S | ✅ Done — Discord/Teams no longer get Slack mrkdwn |
| 7 | **Playwright web-scraper source** | M | ⬜ Biggest portfolio item; optional extra (`autoflow[web]`) so the offline path is untouched |
| 8 | SQLite state backend | M | ⬜ Fixes unbounded JSON growth + daily state commits. Needs `autoflow migrate-state` and JSON as default for YAML compatibility |

---

## Later — depth

| # | Item | Effort | Notes |
|---|------|--------|-------|
| 13 | Pipeline DAG (fanout / merge) | L | The architecturally interesting one. Do it *after* SQLite state, since branches need per-branch dedup scoping. Requires a YAML schema v2 — keep v1 configs working. |
| 14 | GitHub Issues sink | M | Nice demo: pipeline that files issues from a changelog feed |
| 15 | LLM content scoring (rank + threshold, not just summarize) | M | Turns the digest from "everything matching a keyword" into "the 5 things worth reading" |
| 16 | Retry + DLQ for sinks | M | Natural follow-on from the deferred-commit fix already landed |
| 17 | Schedule-builder CLI wizard | M | Generates `digest.yml` from a pipeline file — good README GIF |
| 18 | Notion source | M | Lower priority; narrower audience |

---

## Gaps worth flagging

- **No `--dry-run` at the pipeline level.** Only the webhook sink honours a
  `dry_run` key. A global `autoflow run --dry-run` that skips all side effects
  (sinks *and* state writes) would make config iteration far less scary. **S.**
- **No rate limiting on sources.** The Reddit source hits the public JSON API
  with no throttle; multiple subreddits in a loop will eventually get 429'd.
- **No coverage measurement.** 11 tests is decent but unmeasured. Add
  `pytest-cov` with a floor in CI — cheap credibility for an open-source repo.
- **README has no output screenshot.** For a portfolio project, a sample digest
  rendered in the README is worth more than another feature.

---

## Metrics to instrument

Once the error webhook exists, have each run emit these to the same channel:

| Metric | Why |
|--------|-----|
| Run success rate (7-day rolling) | Would have caught this outage on day 1 |
| Items fetched → filtered → deduped → delivered | Shows *where* a config is too aggressive |
| Dedup hit rate | Rising toward 100% means the source is stale or the filter is too narrow |
| Per-source fetch latency + error count | Tells you which source to add retries to |
| LLM tokens + estimated cost per run | Keeps the OpenAI path honest |
| State-file size | Early warning for the SQLite migration |
