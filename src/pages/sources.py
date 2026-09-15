"""SourcesPage — shows all three sources (PC/CLAW/CODEX) with mini mascots."""
from .base import Page


class SourcesPage(Page):
    name = "Sources"

    def render(self, gfx, d, st, oc, dl, ctx):
        srcs = ctx["sources"]
        gfx.frame(d, "SOURCES", f"{sum(1 for s in srcs if s['online'])}/3 up")
        mascot = ctx["mascot"]
        for i, s in enumerate(srcs):
            cx = 27 + i * 53
            mascot.draw_mini(d, s["key"], cx, 23, s["busy"])
            w = d.textlength(s["label"], font=gfx.font_small)
            gfx.text(d, (int(cx - w / 2), 31), s["label"], small=True)
            if s["busy"]:
                d.rectangle([cx - 2, 40, cx + 2, 41], fill=255)
            elif s["online"]:
                d.rectangle([cx - 2, 40, cx + 2, 41], outline=255)
            else:
                d.line([(cx - 2, 40), (cx + 2, 41)], fill=255)
                d.line([(cx - 2, 41), (cx + 2, 40)], fill=255)
