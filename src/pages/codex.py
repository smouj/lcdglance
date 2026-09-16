"""CodexPage — a dedicated page for the Codex coding agent.

Turns the LCD into a physical terminal for the agent: what it is doing,
which repo, how recently it acted.

States:
  WORKING  — codex_active and a repo/log is known
  IDLE     — seen before but quiet
  OFFLINE  — never seen

The repo name comes from the probe's C2| line when available; otherwise
the last known activity age is shown.
"""
import time

from .base import Page
from ..util.text import clip, age_str


class CodexPage(Page):
    name = "Codex"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        active = bool(s.get("codex_active"))
        seen = bool(s.get("codex_seen"))
        last = s.get("codex_last", "")

        if active:
            header = "WORKING"
        elif seen:
            header = "IDLE"
        else:
            header = "OFFLINE"

        gfx.frame(d, "CODEX", header)

        y = 13
        if not seen:
            gfx.text(d, (3, y), "no codex activity", small=True)
            y += 10
            gfx.text(d, (3, y), "waiting for first run", small=True)
            return

        # Robot face: eyes change with state
        cx, cy = 20, 24
        d.rounded_rectangle([cx - 11, cy - 9, cx + 11, cy + 9],
                            radius=3, outline=255)
        if active:
            # Focused eyes
            d.rectangle([cx - 7, cy - 5, cx - 4, cy - 2], fill=255)
            d.rectangle([cx + 4, cy - 5, cx + 7, cy - 2], fill=255)
            # Thinking dots below
            phase = int(time.time() * 2) % 3
            for i in range(3):
                if i <= phase:
                    d.rectangle([cx - 6 + i * 5, cy + 4, cx - 4 + i * 5, cy + 5], fill=255)
        else:
            # Closed eyes
            d.line([(cx - 7, cy - 3), (cx - 4, cy - 3)], fill=255)
            d.line([(cx + 4, cy - 3), (cx + 7, cy - 3)], fill=255)

        # Right column
        rx = 38
        y = 13
        if active:
            gfx.text(d, (rx, y), "CODING", small=True)
        else:
            gfx.text(d, (rx, y), "quiet", small=True)
        y += 10

        if last:
            gfx.text(d, (rx, y), clip(last, 20), small=True)
            y += 10
        else:
            gfx.text(d, (rx, y), "no recent log", small=True)
            y += 10

        age = s.get("codex_mtime", 0)
        if age:
            gfx.text(d, (rx, y), f"last {age_str(age)} ago", small=True)
