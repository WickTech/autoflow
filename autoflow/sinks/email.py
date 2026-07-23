"""Email a digest over SMTP. Stdlib only — no new dependencies.

Sends a multipart message: plain text for clients that want it, HTML for those
that don't. Like every other sink, a missing configuration is a skip with a
warning, not a crash — the offline path must stay runnable with zero secrets.
"""
from __future__ import annotations

import smtplib
from datetime import date
from email.message import EmailMessage  # stdlib: absolute import, not this module

from .. import env, render
from ..log import log
from ..models import Item
from ..registry import sink
from .base import Sink

DEFAULT_PORT = 587
DEFAULT_TIMEOUT = 30.0


@sink("email")
class EmailSink(Sink):
    """Deliver items as an SMTP email.

    YAML config keys:
      to: list[str] | str     # required
      from: str               # defaults to username
      subject: str            # date is appended
      host: str               # ${SMTP_HOST}
      port: int               # 587 (STARTTLS) or 465 (implicit TLS)
      username / password: str
      starttls: bool          # default true; ignored when ssl is true
      ssl: bool               # implicit TLS, for port 465
    """

    config_keys = (
        "to", "from", "subject", "host", "port", "username", "password",
        "starttls", "ssl", "dry_run", "timeout",
    )
    required_keys = ("to",)

    def emit(self, items: list[Item]) -> None:
        host = env.resolve(self.config.get("host", "${SMTP_HOST}"))
        recipients = self._recipients()
        if not host or not recipients:
            log.warning("email sink skipped (host or recipients not configured)")
            return
        if not items:
            return

        username = env.resolve(self.config.get("username", "${SMTP_USERNAME}"))
        password = env.resolve(self.config.get("password", "${SMTP_PASSWORD}"))
        sender = env.resolve(self.config.get("from")) or username
        if not sender:
            log.warning("email sink skipped (no 'from' address and no username)")
            return

        message = self._build(items, sender, recipients)

        if self.config.get("dry_run"):
            log.info("dry-run email to %s:\n%s", ", ".join(recipients), message["Subject"])
            return

        self._send(message, host, username, password)
        log.info(
            "emailed %d item(s) to %d recipient(s)",
            len(items),
            len(recipients),
            extra={"items": len(items), "recipients": len(recipients)},
        )

    # --- helpers -----------------------------------------------------------

    def _recipients(self) -> list[str]:
        raw = self.config.get("to") or []
        if isinstance(raw, str):
            raw = [raw]
        resolved = [env.resolve(entry).strip() for entry in raw]
        return [address for address in resolved if address]

    def _build(self, items: list[Item], sender: str, recipients: list[str]) -> EmailMessage:
        subject = self.config.get("subject", "autoflow digest")
        message = EmailMessage()
        message["Subject"] = f"{subject} — {date.today().isoformat()}"
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message.set_content(render.render_text(items, style="plain"))
        message.add_alternative(
            render.render_html_document(items, title=subject), subtype="html"
        )
        return message

    def _send(self, message: EmailMessage, host: str, username: str, password: str) -> None:
        port = int(self.config.get("port", DEFAULT_PORT))
        timeout = float(self.config.get("timeout", DEFAULT_TIMEOUT))
        use_ssl = bool(self.config.get("ssl", False))

        opener = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with opener(host, port, timeout=timeout) as server:
            if not use_ssl and self.config.get("starttls", True):
                server.starttls()
            if username and password:
                server.login(username, password)
            server.send_message(message)
