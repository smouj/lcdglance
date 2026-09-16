"""NowPage — instant summary of what's happening right now.

The landing page: PC status, OpenClaw and Codex activity, and network
speed, all in 4 compact lines. At a glance you know everything.
"""
import time

from .base import Page
from ..util.text import clip, fmt_speed, age_str


class NowPage(Page):
    name = "Now"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        srcs = ctx.get("sources", [])
        active = ctx.get("active_source", {})
        busy = ctx.get("busy", False)

        # Header: NOW + clock
        gfx.frame(d, "NOW", "all systems" if not busy else "active")

        y = 13
        # Line 1: PC
        cpu = st.get("cpu", 0)
        mem = st.get("mem", 0)
        cpu_icon = "!" if cpu > 90 else ("." if cpu > 55 else " ")
        gfx.text(d, (3, y), f"PC", small=True)
        gfx.text(d, (22, y), f"{cpu_icon} CPU {cpu:3.0f}%  RAM {mem:3.0f}%", small=True)
        y += 10

        # Line 2: OpenClaw
        oc_state = s.get("state", "offline")
        if s.get("online") or s.get("state") == "stale":
            running = s.get("running", 0)
            if running > 0:
                oc_label = f"{running} running"
            elif s.get("ok", 0) > 0:
                oc_label = "ok"
            else:
                oc_label = "idle"
            oc_icon = "*" if running > 0 else " "
        else:
            oc_label = "offline"
            oc_icon = "x"
        gfx.text(d, (3, y), "CLAW", small=True)
        gfx.text(d, (30, y), f"{oc_icon} {oc_label}", small=True)
        y += 10

        # Line 3: Codex
        codex_active = s.get("codex_active", False)
        codex_last = s.get("codex_last", "")
        if s.get("codex_seen"):
            if codex_active:
                cx_label = clip(codex_last, 18) if codex_last else "working"
                cx_icon = "*"
            else:
                age = s.get("codex_mtime", 0)
                if age:
                    cx_label = f"{age_str(age)} ago"
                else:
                    cx_label = "seen"
                cx_icon = " "
        else:
            cx_label = "not found"
            cx_icon = " "
        gfx.text(d, (3, y), "CODEX", small=True)
        gfx.text(d, (35, y), f"{cx_icon} {cx_label}", small=True)
        y += 10

        # Line 4: Network + download state
        dl_snap = dl.snapshot()
        dn = st.get("net_dn", 0)
        up = st.get("net_up", 0)
        dl_state = dl_snap.get("state", "idle")
        if dl_snap.get("active"):
            net_line = f"DN {fmt_speed(dn)}  {clip(dl_snap.get('name', dl_snap.get('file', '')), 12)}"
        elif dl_state == "confirming":
            net_line = f"DN {fmt_speed(dn)}  confirming..."
        elif dl_state == "candidate":
            net_line = f"DN {fmt_speed(dn)}  detecting..."
        else:
            net_line = f"DN {fmt_speed(dn)}  UP {fmt_speed(up)}"
        gfx.text(d, (3, y), "NET", small=True)
        gfx.text(d, (22, y), net_line, small=True)
