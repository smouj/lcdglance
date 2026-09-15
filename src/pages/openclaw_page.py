"""OpenClawPage — subagent counts, last job, connection status."""
from .base import Page
from ..util.text import clip, age_str


class OpenClawPage(Page):
    name = "OpenClaw"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        gfx.frame(d, "OPENCLAW", "link up" if s["online"] else "OFFLINE")
        if s["online"]:
            gfx.text(d, (3, 13), f"run {s['running']}  ok {s['ok']}  fail {s['fail']}", small=True)
            gfx.text(d, (3, 23), clip(s["last_task"], 25), small=True)
            poll = age_str(s["last_poll_ok"]) if s["last_poll_ok"] else "--"
            gfx.text(d, (3, 33), f"{clip(s['last_task_status'], 12)} poll {poll}", small=True)
        else:
            gfx.text(d, (3, 15), "bridge offline", small=True)
            gfx.text(d, (3, 25), "wsl lcd-probe", small=True)
            gfx.text(d, (3, 35), "not responding", small=True)
