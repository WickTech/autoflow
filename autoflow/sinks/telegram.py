"""Send a digest to a Telegram chat via the Bot API.

No SDK — it's one POST, so it goes through :mod:`autoflow.net` and inherits the
same retry policy as every other network call.

Setup: talk to @BotFather to create a bot and get a token, then message your bot
once and read your chat id from ``https://api.telegram.org/bot<token>/getUpdates``.
"""
from __future__ import annotations

from .. import env, net, render
from ..log import log
from ..models import Item
from ..registry import sink
from .base import Sink

_API = "https://api.telegram.org"

# Telegram rejects anything longer outright, so long digests are split.
MAX_MESSAGE_CHARS = 4096

# Telegram's "MarkdownV2" escaping rules are famously painful; HTML is the
# forgiving option and renders identically for our purposes.
_PARSE_MODES = {"html": "HTML", "markdown": "Markdown", "plain": None}


@sink("telegram")
class TelegramSink(Sink):
    """Deliver items to a Telegram chat.

    YAML config keys:
      token: str        # ${TELEGRAM_BOT_TOKEN}
      chat_id: str      # ${TELEGRAM_CHAT_ID}
      header: str       # optional first line
      format: str       # html (default) | markdown | plain
      disable_preview: bool
    """

    config_keys = (
        "token", "chat_id", "header", "format", "disable_preview",
        "dry_run", "timeout", "retries",
    )

    def emit(self, items: list[Item]) -> None:
        token = env.resolve(self.config.get("token", "${TELEGRAM_BOT_TOKEN}"))
        chat_id = env.resolve(self.config.get("chat_id", "${TELEGRAM_CHAT_ID}"))
        if not token or not chat_id:
            log.warning("telegram sink skipped (token or chat_id not configured)")
            return
        if not items:
            return

        style = self.config.get("format", "html")
        if style not in _PARSE_MODES:
            raise ValueError(f"telegram format must be one of {sorted(_PARSE_MODES)}")

        text = render.render_text(items, header=self.config.get("header", ""), style=style)
        messages = render.chunk(text, MAX_MESSAGE_CHARS)

        if self.config.get("dry_run"):
            log.info("dry-run telegram payload (%d message(s)):\n%s", len(messages), text)
            return

        for part in messages:
            payload: dict = {
                "chat_id": chat_id,
                "text": part,
                "disable_web_page_preview": bool(self.config.get("disable_preview", True)),
            }
            if _PARSE_MODES[style]:
                payload["parse_mode"] = _PARSE_MODES[style]

            resp = self._send(token, payload)
            if "parse_mode" in payload and _is_parse_error(resp):
                # One malformed title would otherwise fail every future run:
                # dedup state is only committed after delivery, so the same
                # item comes back tomorrow. Deliver it unformatted instead.
                log.warning("telegram rejected the %s markup; resending as plain text", style)
                payload.pop("parse_mode")
                resp = self._send(token, payload)
            net.raise_for_status(resp)

        log.info(
            "sent %d item(s) to telegram in %d message(s)",
            len(items),
            len(messages),
            extra={"items": len(items), "messages": len(messages)},
        )

    def _send(self, token: str, payload: dict):
        return net.post(
            f"{_API}/bot{token}/sendMessage",
            json=payload,
            timeout=float(self.config.get("timeout", net.DEFAULT_TIMEOUT)),
            retries=int(self.config.get("retries", net.DEFAULT_RETRIES)),
        )


def _is_parse_error(resp) -> bool:
    """Telegram answers malformed markup with 400 "can't parse entities"."""
    return resp.status_code == 400 and "can't parse entities" in resp.text
