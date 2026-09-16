"""NowPage — instant summary of what's happening right now.

The landing page. The panel body only fits THREE 10 px text lines below the
12 px header (43 - 12 = 31 px), so the network figures live in the header
line and the body carries the three sources.

Layout (160x43):
  Header : NOW  <net summary>       HH:MM  ....dots
  Line 1 : PC     CPU 42%  RAM 68%
  Line 2 : CLAW   * 2 running
  Line 3 : CODEX  * editing ...
"""
import time

from .base import Page
from ..util.text import clip, fmt_speed, age_str


class NowPage(Page):
    name = "Now"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        busy = ctx.get("busy", False)
        dl_snap = dl.snapshot()
        dl_state = dl_snap.get("state", "idle")

        # Header carries the network summary; the body only fits 3 lines.
        # Keep this string short: the frame drops `right` text that would
        # collide with the title or the clock.
        dn = st.get("net_dn", 0)
        if dl_state in ("confirming", "candidate"):
            head = "* detecting"
        else:
            # "v" reads as a down arrow; the full "DN x/y" form is too wide
            # for the header zone with ten page dots.
            head = "v" + fmt_speed(dn)
        gfx.frame(d, "NOW", head)

        y = 13
        # Line 1: the PC
        cpu = st.get("cpu", 0)
        mem = st.get("mem", 0)
        cpu_mark = "!" if cpu > 90 else ("*" if cpu > 55 else " ")
        gfx.text(d, (3, y), "PC", small=True)
        gfx.text(d, (30, y), f"{cpu_mark} CPU {cpu:3.0f}%  RAM {mem:3.0f}%", small=True)
        y += 10

        # Line 2: OpenClaw
        if s.get("online") or s.get("state") == "stale":
            running = s.get("running", 0)
            if running > 0:
                oc_label, oc_mark = f"{running} running", "*"
            elif s.get("fail", 0) > 0:
                oc_label, oc_mark = f"{s.get('fail', 0)} failed", "!"
            else:
                oc_label, oc_mark = "idle", " "
        else:
            oc_label, oc_mark = "offline", "x"
        gfx.text(d, (3, y), "CLAW", small=True)
        gfx.text(d, (38, y), f"{oc_mark} {oc_label}", small=True)
        y += 10

        # Line 3: Codex
        if s.get("codex_seen"):
            if s.get("codex_active"):
                cx_label, cx_mark = clip(s.get("codex_last", "") or "working", 16), "*"
            else:
                mtime = s.get("codex_mtime", 0)
                cx_label = f"{age_str(mtime)} ago" if mtime else "seen"
                cx_mark = " "
        else:
            cx_label, cx_mark = "not found", " "
        gfx.text(d, (3, y), "CODEX", small=True)
        gfx.text(d, (43, y), f"{cx_mark} {cx_label}", small=True)
