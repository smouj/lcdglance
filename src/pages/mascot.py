"""MascotPage — the main mascot + status display page.

Layout (160x43):
  Header band y=0..11     : HH:MM clock (right), page dots (far right)
  Left column x=0..56     : mascot art + ground line
  Separator  x=58         : vertical rule
  Right column x=63..159  : three lines, 10 px apart, starting below the
                            header band so nothing overlaps the clock:
                              y=12  <LABEL> <STATE>      (big font)
                              y=22  <model>              (small font)
                              y=32  <usage / cost left>  (small font)

The model + quota lines come from the OpenClaw probe (M| and U| lines) and
degrade gracefully: with no probe data the lines fall back to the source
detail and the load index.
"""
import time

from .base import Page
from ..util.text import clip


def _short_model(model):
    """'deepseek/deepseek-flash' -> 'deepseek-flash'."""
    m = (model or "").strip()
    return m.split("/", 1)[1] if "/" in m else m


def _usage_text(s):
    """Remaining quota as one compact line, or '' when unknown."""
    bal = (s.get("usage_balance") or "").strip()
    wlab = (s.get("usage_window_label") or "").strip()
    wpct = (s.get("usage_window_pct") or "").strip()
    if bal:
        return f"{bal} left"
    if wlab and wpct.lstrip("-").isdigit():
        left = max(0, 100 - int(wpct))
        return f"{wlab} {left}% left"
    return ""


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

        # --- Right column body (starts below the 12 px header band) ---
        s = oc.snapshot()
        state = "BUSY" if src["busy"] else ("OK" if src["online"] else "OFFLINE")
        gfx.text(d, (63, 12), clip(f"{src['label']} {state}", 12))

        model = _short_model(s.get("model"))
        gfx.text(d, (63, 22), clip(model, 15) if model else clip(src["detail"], 15),
                 small=True)

        usage = _usage_text(s)
        gfx.text(d, (63, 32),
                 clip(usage, 15) if usage else f"LOAD {ctx.get('load', 0):,}",
                 small=True)
