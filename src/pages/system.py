"""SystemPage — CPU / RAM / disk bars with sparklines from history buffers."""
from .base import Page


class SystemPage(Page):
    name = "System"

    def render(self, gfx, d, st, oc, dl, ctx):
        gfx.frame(d, "SYSTEM", fmt_uptime(st.get("uptime", 0)))
        y = 13
        hist_bufs = ctx.get("hist_bufs", {})
        for label, pct, key in (("CPU", st.get("cpu", 0), "cpu"),
                                 ("RAM", st.get("mem", 0), "ram"),
                                 ("DSK", st.get("disk", 0), "disk")):
            gfx.text(d, (3, y), f"{label} {pct:5.1f}%", small=True)
            gfx.hbar(d, 62, y + 1, 95, 8, pct / 100.0)
            # Sparkline from history buffer if available
            buf = hist_bufs.get(key)
            if buf and len(buf) >= 3:
                gfx.sparkline(d, 62, y + 1, 95, 8, buf)
            y += 10


from ..util.text import fmt_uptime
