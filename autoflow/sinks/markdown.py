"""Render items into a Markdown digest file."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from ..log import log
from ..models import Item
from ..registry import sink
from .base import Sink


@sink("markdown")
class MarkdownSink(Sink):
    config_keys = ("path", "title")

    def emit(self, items: list[Item]) -> None:
        path = Path(self.config.get("path", "out/digest.md"))
        path.parent.mkdir(parents=True, exist_ok=True)
        title = self.config.get("title", "Digest")

        lines = [f"# {title} — {date.today().isoformat()}", ""]
        if not items:
            lines.append("_No new items._")
        for item in items:
            heading = f"## [{item.title}]({item.url})" if item.url else f"## {item.title}"
            lines.append(heading)
            if item.summary:
                lines.append("")
                lines.append(item.summary)
            if item.source:
                lines.append("")
                lines.append(f"<sub>source: {item.source}</sub>")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        log.info(
            "wrote %d item(s) → %s", len(items), path,
            extra={"sink": "markdown", "path": str(path), "items": len(items)},
        )
