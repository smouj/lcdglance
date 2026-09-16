"""SystemPage — CPU / RAM / disk with real units and clean bars.

Vertical budget for the 160x43 panel:
    header  0..12   (the shared rule is drawn at y=12)
    body   13..42   (30 px)
The small font draws 8 px glyphs, so only THREE text rows fit readably
(13, 23, 33). A fourth "LOAD" row would either fall off the panel or, if
packed tighter, collide with the row above — so the load graph lives on
NetworkPage, where it has the room to be the protagonist.

Bars carry no sparkline overlay: a graph drawn on top of a bar makes both
unreadable.
"""
from .base import Page
from ..util.text import clip, fmt_uptime


def _best_temp(temps, default="--"):
    """Most relevant temperature: core/package before any other sensor."""
    if not temps:
        return default
    for label, value in temps:
        low = label.lower()
        if "core" in low or "cpu" in low or "package" in low or "tctl" in low:
            return f"{value:.0f}C"
    return f"{temps[0][1]:.0f}C"


def _gb(n):
    """Format a value already in gigabytes: 9.9G, 267G, 1.2T."""
    if n >= 1024:
        return f"{n / 1024:.1f}T"
    return f"{n:.0f}G" if n >= 100 else f"{n:.1f}G"


class SystemPage(Page):
    name = "System"

    def render(self, gfx, d, st, oc, dl, ctx):
        gfx.frame(d, "SYSTEM", fmt_uptime(st.get("uptime", 0)))

        rows = (
            ("CPU", st.get("cpu", 0), _best_temp(st.get("temps", []))),
            ("RAM", st.get("mem", 0),
             f"{st.get('mem_used', 0):.1f}/{st.get('mem_total', 0):.0f}G"),
            ("DSK", st.get("disk", 0),
             f"{_gb(st.get('disk_total', 0) - st.get('disk_used', 0))} free"),
        )

        y = 13
        for label, pct, detail in rows:
            gfx.text(d, (3, y), f"{label} {pct:3.0f}%", small=True)
            gfx.hbar(d, 52, y + 1, 52, 8, pct / 100.0)
            gfx.text(d, (110, y), clip(str(detail), 11), small=True)
            y += 10
