"""AlertsPage — system + agent alerts with severity icons."""
import time

from .base import Page, _alert_icon
from ..util.constants import RGB_STATE
from ..util.text import clip, age_str


class AlertsPage(Page):
    name = "Alerts"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        items = []
        now = time.time()
        if st.get("cpu", 0) > 90:
            items.append((now, "fail", f"CPU HIGH {st['cpu']:.0f}%"))
        if st.get("mem", 0) > 90:
            items.append((now, "fail", f"RAM HIGH {st['mem']:.0f}%"))
        if st.get("disk", 0) > 95:
            items.append((now, "fail", f"DISK {st['disk']:.0f}%"))
        for ts, kind, text in s["alerts"][-6:]:
            items.append((ts, kind, text))

        if not items:
            gfx.frame(d, "ALERTS", "none")
            gfx.text(d, (3, 15), "all systems ok", small=True)
            gfx.text(d, (3, 25), f"agents {s['ok']} ok {s['fail']} fail", small=True)
            return
        gfx.frame(d, f"ALERTS ({len(items)})", RGB_STATE["effect"][:11])
        y = 13
        for ts, kind, text in items[-3:]:
            _alert_icon(d, 2, y + 1, kind)
            gfx.text(d, (12, y), f"{clip(text, 23)} {age_str(ts)}", small=True)
            y += 10
