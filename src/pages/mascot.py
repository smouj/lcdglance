"""MascotPage — the main mascot + status display page."""
from .base import Page


class MascotPage(Page):
    name = "Mascot"

    def render(self, gfx, d, st, oc, dl, ctx):
        mascot = ctx["mascot"]
        src = ctx["active_source"]
        mood = ctx["mood"]
        mascot.draw(d, src["key"], 29, 18, mood, busy=ctx.get("busy", False))
        d.line([(6, 38), (52, 38)], fill=255)     # ground line
        d.line([(58, 1), (58, 41)], fill=255)     # column separator
        gfx.page_dots(d)
        gfx.text(d, (63, 0), src["label"])
        gfx.text(d, (63, 15), clip(src["detail"], 15), small=True)
        state = "BUSY" if src["busy"] else ("OK" if src["online"] else "OFFLINE")
        gfx.text(d, (63, 25), state, small=True)
        gfx.text(d, (63, 34), f"LOAD {ctx.get('load', 0):,}", small=True)


from ..util.text import clip
