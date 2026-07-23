# autoflow — Code Review & Audit

**Date:** 2026-07-20 · **Reviewed at:** `master` @ `458b44b` + uncommitted working tree
**Scope:** full repo (9 modules, 4 test files, 2 workflows)

---

## 1. Why the Daily Digest has failed every weekday since ~1 July

**Root cause:** `.github/workflows/digest.yml` ran

```bash
git add out/ .autoflow_state.json
```

but both paths are listed in `.gitignore` (lines 11–12). `git add` on an ignored
path exits **1** with *"The following paths are ignored by one of your .gitignore
files"*. The step fails, the job fails, the digest is never committed.

This matches the failure signature exactly: same commit, every scheduled run,
2 annotations, dead in 14–21 s.

**Why it went unnoticed for 3 weeks:** `ci.yml` triggered on `push: branches: [main]`,
but this repo's default branch is **`master`**. CI has never run on a push. The
only signal was the GitHub notification email.

**Fixed:** `git add -f`, guarded for missing paths, plus rebase-before-push and a
`concurrency` group so two runs can't race.

---

## 2. Findings

### P0 — blocking (all fixed in this pass)

| # | Finding | File | Fix |
|---|---------|------|-----|
| 1 | `git add` on gitignored paths exits 1 → digest fails daily | `digest.yml` | `git add -f`, existence guard |
| 2 | CI never triggers — watches `main`, repo is on `master` | `ci.yml` | `branches: [main, master]` + `workflow_dispatch` |
| 3 | Uncommitted Reddit tests carry an unused `import json` → `ruff check` fails on the first green CI run | `tests/test_reddit.py` | import removed; also fixed a no-op `mock_get.call_count == 2` assertion |

### P1 — correctness & operability

**4. Dedup state was persisted before delivery — permanent item loss.** *(fixed)*
`DedupProcessor.process()` called `store.save()` inline, so if a sink raised
(webhook 500, disk full), items were already marked seen and **never resurfaced**.
Persistence is now deferred: `Processor.commit()` is called by the runner only
after every sink succeeds. Regression test added
(`test_dedup_state_not_persisted_when_a_sink_fails`).

**5. No push-race protection.** *(fixed)* Scheduled run + a human push = rejected
push. Now `git pull --rebase --autostash` and a `concurrency: daily-digest` group.

**6. Failures are invisible.** *(fixed)* The only failure channel was GitHub's
email, which is easy to filter into oblivion — as happened here. Both workflows
now have an `if: failure()` step posting the job, branch, commit, and run URL to
`AUTOFLOW_ERROR_WEBHOOK_URL`. No secret configured = silent no-op, so the
zero-config path is preserved. **Set that repo secret.**

**7. Unbounded state growth.** `.autoflow_state.json` is a plain JSON array with
no TTL or cap. At ~30 items/day that's ~7.5k fingerprints/year, rewritten and
committed to git *every weekday*. Needs a max-size or age-based eviction —
fingerprints older than the source's retention window can never re-appear anyway.

**8. No retry on source fetch.** *(fixed)* One `hnrss.org` timeout or 503 failed
the entire run. All source HTTP now goes through `autoflow/net.py`, which retries
transport errors and transient statuses (408/425/429/5xx) with exponential
backoff, full jitter, and `Retry-After` support. 4xx still fails fast. Tunable
per-source via `retries:` / `timeout:` in YAML.

**9. No config validation.** *(fixed)* `_build()` splatted YAML keys straight into
the plugin constructor, so `limt: 30` was silently accepted. Plugins now declare
`config_keys` / `required_keys` via the `ConfigSpec` mixin, and
`autoflow validate <file>...` reports unknown components, missing `type`, typo'd
keys, unset `${ENV_VAR}` references, and sink-less pipelines. Declaring nothing
disables the check, so third-party plugins are unaffected. Wired into CI.

**10. `SeenStore.save()` is non-atomic.** *(fixed)* An interrupted `write_text`
truncated the file; the `except JSONDecodeError` path then silently reset `_seen`
to **empty** and the next run re-delivered everything. Now writes to a temp file
in the same directory, `fsync`s, and `os.replace`s.

### P2 — quality & polish

**11. `keyword_filter` does naive substring matching.** *(fixed)* `include: [ai]`
matched "ch**ai**r", "s**ai**d", "Ukr**ai**ne" — and this is the flagship example
config, so digest quality suffered visibly. Now word-boundary regex with phrase
support ("machine learning" matches across whitespace); `substring: true` restores
the old behaviour. Existing YAML keeps working unchanged.

**12. Webhook sink is Slack-only despite the docstring.** *(fixed)* It emitted
Slack mrkdwn links (`<url|title>`), which Discord and Teams render literally.
There is now a `format:` key — `slack` (default, so existing configs are
unchanged), `markdown`, `html`, `plain` — backed by a shared `render.py` that
the Telegram and email sinks reuse.

**12b. Webhook delivery had no retries.** *(fixed)* The sink called `httpx.post`
directly, bypassing the retry layer — so sources retried transient failures but
delivery did not. That got worse once dedup state was deferred until sinks
succeed: one 503 deferred a whole digest. Now goes through `net.post`, with
`retries:` / `timeout:` config keys.

**13. Unsafe XML parsing.** *(fixed)* `RssSource._parse` ran `ET.fromstring` on
remote input, exposing it to entity-expansion ("billion laughs") DoS. Now uses
`defusedxml.ElementTree` (added to `dependencies`) with a stdlib fallback so
existing installs don't break.

**14. No LLM timeout or cost ceiling.** *(fixed)* `llm.summarize` called OpenAI
with no `timeout=`, no retry, and no token budget — a hung call would block the
job until the 6-hour Actions limit. Now bounded by `AUTOFLOW_LLM_TIMEOUT`,
`AUTOFLOW_LLM_RETRIES`, `AUTOFLOW_LLM_MAX_TOKENS`, and a per-run
`AUTOFLOW_LLM_TOKEN_BUDGET`. Any failure — timeout, rate limit, budget exhausted,
empty response — degrades to the extractive summarizer instead of failing the
run, and token usage is logged at the end of each run.

**15. Test isolation gap.** *(fixed)* `conftest.py` unset `OPENAI_API_KEY` /
`OPENAI_BASE_URL` but **not** `AUTOFLOW_WEBHOOK_URL`, so a developer with that
exported would have had the suite post to a live Slack channel. Both webhook vars
are now unset by the autouse fixture, and retry backoff never really sleeps.

**16. `print()` everywhere, no structured logging.** *(fixed)* `autoflow/log.py`
adds levels and a JSON formatter (`--log-level`, `--log-format json`, or the
`AUTOFLOW_LOG_*` env vars). Diagnostics go to **stderr**; the console sink keeps
`print` on **stdout** deliberately, so `autoflow run ... > digest.txt` still
captures the digest rather than the log noise.

---

## 3. What's good

- Registry + decorator plugin model is clean; adding a source really is zero
  runner edits. The Reddit source proves it.
- Offline-first is genuinely honoured — the extractive summarizer is
  deterministic and the whole suite runs with no secrets and no network.
- `Item.fingerprint` is stable and URL-first, which is the right call.
- Stdlib-only RSS parsing (no `feedparser`) keeps the dependency tree tiny.
- YAML configs are readable and the examples double as documentation.

---

## 4. Verification status

⚠️ **Tests were not executed in this session** — the shell sandbox could not mount
the WSL path, so `pytest -q` and `ruff check` could not be run. All changes were
made by inspection. Before pushing, please run locally:

```bash
ruff check autoflow tests && pytest -q
autoflow run examples/offline-demo.yaml
```

Then trigger the digest manually (**Actions → Daily Digest → Run workflow**)
rather than waiting for tomorrow's 08:00 UTC cron.

Also note: `autoflow/sources/reddit.py` and `tests/test_reddit.py` are **not yet
committed**. They should go up in the same PR as these fixes.
