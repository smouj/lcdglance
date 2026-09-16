"""DownloadPage — shows when a download is active (auto-focus).

Layout:
  Progress bar + name + speed + ETA when downloading.
  Shows detection state (candidate/confirming/stalled) when not yet active.
"""
import time

from .base import Page
from ..util.text import clip, fmt_speed, fmt_bytes


class DownloadPage(Page):
    name = "Download"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = dl.snapshot()
        state = s.get("state", "idle")

        if state == "stalled":
            # A stalled transfer is still `active` (the panel keeps watching
            # it); the stall view is what tells the user data stopped moving.
            gfx.frame(d, "DOWNLOAD", "stalled")
            gfx.text(d, (3, 20), "download stalled", small=True)
            gfx.text(d, (3, 30),
                     f"{fmt_bytes(s.get('total_mb', 0))}  waiting for data...",
                     small=True)
        elif s.get("active"):
            elapsed = int(s.get("elapsed", 0))
            speed = s.get("speed", 0)
            total_mb = s.get("total_mb", 0)
            file_mb = s.get("file_mb", 0)
            name = s.get("name", "") or s.get("file", "")

            # Progress bar
            pct = (total_mb / file_mb) if file_mb > 0 else 0
            gfx.frame(d, "DOWNLOAD", fmt_speed(speed))
            gfx.stripes(d, 2, 13, 156, 10, time.time() * 26)
            gfx.hbar(d, 2, 24, 156, 8, min(1.0, pct))

            # Name or elapsed
            if int(time.time()) % 2 == 0:
                gfx.text(d, (3, 34), f"{clip(name, 12)} {fmt_bytes(total_mb)}", small=True)
            else:
                gfx.text(d, (3, 34), f"{elapsed}s  {fmt_bytes(total_mb)}/{fmt_bytes(file_mb)}", small=True)
        elif state == "confirming":
            gfx.frame(d, "DOWNLOAD", "confirming")
            gfx.text(d, (3, 20), "detecting download...", small=True)
            gfx.text(d, (3, 30), f"DN {fmt_speed(st.get('net_dn', 0))}", small=True)
        elif state == "candidate":
            gfx.frame(d, "DOWNLOAD", "detecting")
            gfx.text(d, (3, 20), "network activity detected", small=True)
            gfx.text(d, (3, 30), f"DN {fmt_speed(st.get('net_dn', 0))}", small=True)
        else:
            # Idle — should not normally be shown
            gfx.frame(d, "DOWNLOAD", "none")
            gfx.text(d, (3, 20), "no active download", small=True)
