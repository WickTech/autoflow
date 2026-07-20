"""Post a digest to an incoming webhook (Slack/Discord/Teams compatible).

The URL can be given inline or, preferably, via an ${ENV_VAR} reference that is
resolved at runtime — so secrets stay out of the committed config.
"""
from __future__ import annotations

import os

import httpx

from ..models import Item
from ..registry import sink
from .base import Sink


@sink("webhook")
class WebhookSink(Sink):
    config_keys = ("url", "header", "dry_run")

    def emit(self, items: list[Item]) -> None:
        url = self._resolve(self.config.get("url", "${AUTOFLOW_WEBHOOK_URL}"))
        if not url:
            print("autoflow: webhook sink skipped (no URL configured).")
            return
        if not items:
            return

        lines = [self.config.get("header", "*New items*")]
        for item in items:
            bullet = f"• <{item.url}|{item.title}>" if item.url else f"• {item.title}"
            if item.summary:
                bullet += f" — {item.summary}"
            lines.append(bullet)

        if self.config.get("dry_run"):
            print("autoflow (dry-run webhook):\n" + "\n".join(lines))
            return

        resp = httpx.post(url, json={"text": "\n".join(lines)}, timeout=20)
        resp.raise_for_status()
        print(f"autoflow: posted {len(items)} item(s) to webhook.")

    @staticmethod
    def _resolve(value: str) -> str:
        if value.startswith("${") and value.endswith("}"):
            return os.getenv(value[2:-1], "")
        return value
