"""SourcesPage — shows all three sources (PC/CLAW/CODEX) with mini mascots.

Each source has:
  - Mini mascot art
  - Status label (OK / BUSY / STALE / OFFLINE / IDLE)
  - Connection state from supervisor
"""
from .base import Page
from ..util.text import clip


def _state_label(src, oc_snap):
    """Human-readable state for a source."""
    key = src["key"]
    if key == "pc":
        return "BUSY" if src["busy"] else "OK"
    # OpenClaw / Codex: use supervisor state
    state = oc_snap.get("state", "offline")
    if src["online"]:
        if src["busy"]:
            return "BUSY"
        return "OK" if state == "online" else "STALE"
    if state == "stale":
        return "STALE"
    if state == "connecting":
        return "..."
    return "OFFLINE"


class SourcesPage(Page):
    name = "Sources"

    def render(self, gfx, d, st, oc, dl, ctx):
        srcs = ctx["sources"]
        oc_snap = oc.snapshot()
        active = ctx.get("active_source", {})
        n_up = sum(1 for s in srcs if s["online"])
        gfx.frame(d, "SOURCES", f"{n_up}/3 up")
        mascot = ctx["mascot"]
        for i, s in enumerate(srcs):
            cx = 27 + i * 53
            # Mini mascot
            mascot.draw_mini(d, s["key"], cx, 21, s["busy"])
            # Label centered below
            label = s["label"]
            w = int(d.textlength(label, font=gfx.font_small))
            gfx.text(d, (int(cx - w / 2), 30), label, small=True)
            # State with supervisor info
            state = _state_label(s, oc_snap) if s["key"] != "pc" else ("BUSY" if s["busy"] else "OK")
            # Activity indicator
            if s["busy"]:
                d.rectangle([cx - 2, 39, cx + 2, 41], fill=255)
            elif s["online"]:
                d.rectangle([cx - 2, 39, cx + 2, 41], outline=255)
            else:
                d.line([(cx - 2, 39), (cx + 2, 41)], fill=255)
                d.line([(cx - 2, 41), (cx + 2, 39)], fill=255)
