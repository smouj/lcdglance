"""MascotPage — the main mascot + status display page."""
import time

from .base import Page
from ..util.text import clip


class MascotPage(Page):
    name = "Mascot"

    def render(self, gfx, d, st, oc, dl, ctx):
        mascot = ctx["mascot"]
        src = ctx["active_source"]
        mood = ctx["mood"]
        mascot.draw(d, src["key"], 29, 18, mood, busy=ctx.get("busy", False))
        d.line([(6, 38), (52, 38)], fill=255)     # ground line
        d.line([(58, 1), (58, 41)], fill=255)     # column separator

        # --- Page dots (top-right) ---
        gfx.page_dots(d)

        # --- Clock in right column, top-right, before dots ---
        t = time.localtime()
        clk = f"{t.tm_hour:2d}:{t.tm_min:02d}"
        # Dots block ends at W-4. Calculate dots_left for clock placement.
        dots = gfx.dots
        if dots:
            dots_left = 160 - 6 - ((dots[1] - 1) * 3 + 3)
        else:
            dots_left = 160 - 2
        clk_w = d.textlength(clk, font=gfx.font_small)
        clk_x = dots_left - 6 - clk_w
        # Clamp: don't overlap column separator (x=58+2=60)
        if clk_x < 62:
            clk_x = 62
        d.text((clk_x, 1), clk, font=gfx.font_small, fill=255)

        # --- Source info in right column ---
        gfx.text(d, (63, 10), src["label"])
        gfx.text(d, (63, 20), clip(src["detail"], 15), small=True)
        state = "BUSY" if src["busy"] else ("OK" if src["online"] else "OFFLINE")
        gfx.text(d, (63, 30), state, small=True)
        gfx.text(d, (63, 38), f"LOAD {ctx.get('load', 0):,}", small=True)
