"""DownloadPage — shows when a download is active (auto-focus)."""
import time

from .base import Page
from ..util.text import clip, fmt_speed, fmt_bytes


class DownloadPage(Page):
    name = "Download"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = dl.snapshot()
        gfx.frame(d, "DOWNLOADING", fmt_speed(s["speed"]))
        gfx.stripes(d, 2, 15, 156, 12, time.time() * 26)
        if int(time.time()) % 2 == 0:
            gfx.text(d, (3, 30), f"{clip(s['name'] or 'download', 11)} {fmt_bytes(s['total_mb'])}", small=True)
        else:
            gfx.text(d, (3, 30), clip(s["file"] or f"{int(s['elapsed'])}s elapsed", 25), small=True)
