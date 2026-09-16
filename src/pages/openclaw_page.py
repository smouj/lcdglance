"""OpenClawPage — subagent counts, last job, connection status with supervisor state.

Shows ONLINE / STALE / OFFLINE / CONNECTING instead of just true/false.
Includes latency and last-poll age when available.
"""
from .base import Page
from ..util.text import clip, age_str


class OpenClawPage(Page):
    name = "OpenClaw"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        state = s.get("state", "offline")

        # Header shows connection state
        if state == "online":
            header = "link up"
        elif state == "stale":
            header = "STALE"
        elif state == "connecting":
            header = "connecting..."
        else:
            header = "OFFLINE"

        gfx.frame(d, "OPENCLAW", header)

        y = 13
        if state in ("online", "stale"):
            running = s.get("running", 0)
            ok = s.get("ok", 0)
            fail = s.get("fail", 0)
            gfx.text(d, (3, y), f"run {running}  ok {ok}  ! {fail}", small=True)
            y += 10

            # Last task
            gfx.text(d, (3, y), clip(s.get("last_task", ""), 25), small=True)
            y += 10

            # Poll info + latency
            poll = age_str(s.get("last_poll_ok", 0)) if s.get("last_poll_ok") else "--"
            latency = s.get("latency", 0)
            lat_str = f"{latency:.1f}s" if latency > 0 else ""
            gfx.text(d, (3, y), f"{clip(s.get('last_task_status', ''), 12)} poll {poll} {lat_str}", small=True)
        else:
            # Offline or connecting: show diagnosis
            fail_count = s.get("fail_count", 0)
            last_err = s.get("last_error", "")
            gfx.text(d, (3, y), "bridge offline", small=True)
            y += 10
            if state == "connecting":
                gfx.text(d, (3, y), "wsl lcd-probe", small=True)
                y += 10
                gfx.text(d, (3, y), "connecting...", small=True)
            else:
                gfx.text(d, (3, y), "wsl lcd-probe", small=True)
                y += 10
                gfx.text(d, (3, y), f"retry in {s.get('backoff', '?')}s  fails={fail_count}", small=True)
