"""ProcsPage — top processes by CPU."""
from .base import Page
from ..util.text import clip


class ProcsPage(Page):
    name = "Procs"

    def render(self, gfx, d, st, oc, dl, ctx):
        gfx.frame(d, "PROCESSES", str(st.get("procs", "?")))
        procs = (st.get("top") or [])
        if not procs:
            gfx.text(d, (3, 20), "sampling...", small=True)
            return
        y = 13
        for p in procs[:3]:
            n = clip(p.get("name") or "?", 14)
            c = p.get("cpu_percent", 0) or 0
            gfx.text(d, (3, y), n, small=True)
            gfx.text(d, (90, y), f"{c:3.0f}%", small=True)
            gfx.hbar(d, 116, y + 1, 41, 8, min(1.0, c / 100.0), outline=True)
            y += 10
