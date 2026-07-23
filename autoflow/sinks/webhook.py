"""Post a digest to an incoming webhook (Slack, Discord, Teams).

The URL can be given inline or, preferably, via an ${ENV_VAR} reference that is
resolved at runtime — so secrets stay out of the committed config.

``format:`` picks the markup dialect. It defaults to ``slack`` for backward
compatibility, but Discord and Teams render Slack's ``<url|title>`` literally —
use ``format: markdown`` there.
"""
from __future__ import annotations

from .. import env, net, render
from ..log import log
from ..models import Item
from ..registry import sink
from .base import Sink


@sink("webhook")
class WebhookSink(Sink):
    config_keys = ("url", "header", "format", "dry_run", "timeout", "retries")

    def emit(self, items: list[Item]) -> None:
        url = env.resolve(self.config.get("url", "${AUTOFLOW_WEBHOOK_URL}"))
        if not url:
            log.warning("webhook sink skipped (no URL configured)")
            return
        if not items:
            return

        text = render.render_text(
            items,
            header=self.config.get("header", "*New items*"),
            style=self.config.get("format", "slack"),
        )

        if self.config.get("dry_run"):
            log.info("dry-run webhook payload:\n%s", text)
            return

        resp = net.post(
            url,
            json={"text": text},
            timeout=float(self.config.get("timeout", net.DEFAULT_TIMEOUT)),
            retries=int(self.config.get("retries", net.DEFAULT_RETRIES)),
        )
        resp.raise_for_status()
        log.info("posted %d item(s) to webhook", len(items), extra={"items": len(items)})
