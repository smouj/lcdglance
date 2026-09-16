"""ActivityPage — recent events timeline.

Shows the last 4-5 events (agent completions, download starts/ends,
alerts) as a compact timeline. More useful than Procs for daily use.
"""
import time

from .base import Page
from ..util.text import clip, age_str


class ActivityPage(Page):
    name = "Activity"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        alerts = s.get("alerts", [])
        dl_snap = dl.snapshot()

        # Build a merged timeline from alerts + download state
        items = []

        # Agent alerts (already sorted by timestamp)
        for ts, kind, text in alerts[-5:]:
            icon = "v" if kind == "ok" else ("!" if kind == "fail" else ".")
            items.append((ts, f"{icon} {clip(text, 24)}"))

        # Download event (if active or recently finished)
        if dl_snap.get("active"):
            items.append((time.time(), f"DN {clip(dl_snap.get('name', dl_snap.get('file', 'download')), 18)}"))

        # Sort by timestamp descending
        items.sort(key=lambda x: x[0], reverse=True)
        items = items[:4]

        if not items:
            gfx.frame(d, "ACTIVITY", "none")
            gfx.text(d, (3, 20), "no recent events", small=True)
            return

        gfx.frame(d, "ACTIVITY", f"{len(items)} events")

        y = 13
        for ts, text in items:
            gfx.text(d, (3, y), clip(text, 24), small=True)
            gfx.text(d, (110, y), age_str(ts), small=True)
            y += 10
