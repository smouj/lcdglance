"""MascotPage — the main mascot + status display page.

Layout (160x43):
  Left column  (0..56)   : mascot sprite + ground line
  Separator    (58)      : vertical rule
  Right column (63..159) : clock (top-right), source label, detail, status

The clock is right-aligned in the header band so it never touches the
page dots (top-right corner) nor the source label (which starts below
the header band, at y=12).
"""
import time

from .base import Page
from ..util.text import clip, fmt_uptime


class MascotPage(Page):
    name = "Mascot"

    def render(self, gfx, d, st, oc, dl, ctx):
        mascot = ctx["mascot"]
        src = ctx["active_source"]
        mood = ctx["mood"]

        # --- Left column: mascot art ---
        mascot.draw(d, src["key"], 29, 18, mood, busy=ctx.get("busy", False))
        d.line([(6, 38), (52, 38)], fill=255)     # ground line
        d.line([(58, 1), (58, 41)], fill=255)     # column separator

        # --- Page dots (extreme top-right) ---
        gfx.page_dots(d)

        # --- Clock (header band, right-aligned before the dots) ---
        t = time.localtime()
        clk = f"{t.tm_hour:2d}:{t.tm_min:02d}"
        dots = gfx.dots
        if dots:
            dots_left = 160 - 6 - ((dots[1] - 1) * 3 + 3)
        else:
            dots_left = 160 - 2
        clk_w = int(d.textlength(clk, font=gfx.font_small))
        clk_x = dots_left - 6 - clk_w
        if clk_x < 62:          # never cross the column separator
            clk_x = 62
        d.text((clk_x, 1), clk, font=gfx.font_small, fill=255)

        # --- Right column body (starts below the 12px header band) ---
        gfx.text(d, (63, 12), clip(src["label"], 8))
        gfx.text(d, (63, 23), clip(src["detail"], 15), small=True)
        state = "BUSY" if src["busy"] else ("OK" if src["online"] else "OFFLINE")
        gfx.text(d, (63, 32), f"{state} {ctx.get('load', 0):,}", small=True)
