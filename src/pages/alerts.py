"""AlertsPage — system + agent alerts with severity icons.

When all systems are normal, shows a calm "ALL SYSTEMS OK" message.
When alerts exist, shows up to 3 with icons and age.
Critical alerts (CPU > 95%, RAM > 95%) use inverted display.
"""
import time

from .base import Page, _alert_icon
from ..util.constants import W, H
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

        # Critical temperature alert
        for label, temp in st.get("temps", []):
            if temp > 90:
                items.append((now, "fail", f"TEMP {temp:.0f}C {label}"))

        # Sort by timestamp descending
        items.sort(key=lambda x: x[0], reverse=True)

        if not items:
            # All clear — calm display
            gfx.frame(d, "ALERTS", "none")
            # Checkmark icon centered
            cx, cy = 80, 23
            d.line([(cx - 6, cy), (cx - 2, cy + 4)], fill=255)
            d.line([(cx - 2, cy + 4), (cx + 6, cy - 5)], fill=255)
            gfx.text(d, (3, 33), f"agents {s.get('ok', 0)} ok {s.get('fail', 0)} fail", small=True)
            return

        n = len(items)
        # Critical: inverted full frame
        if any(kind == "fail" for _, kind, _ in items[:1]):
            d.rectangle([0, 0, W - 1, H - 1], fill=255)
            gfx.text(d, (3, 3), f"! ALERTS ({n})", small=True)
            y = 15
            for ts, kind, text in items[:3]:
                icon = "!" if kind == "fail" else ("v" if kind == "ok" else ".")
                gfx.text(d, (3, y), f"{icon} {clip(text, 23)} {age_str(ts)}", small=True)
                y += 10
            return

        # Normal alert display
        gfx.frame(d, f"ALERTS ({n})", "")
        y = 13
        for ts, kind, text in items[-3:]:
            _alert_icon(d, 2, y + 1, kind)
            gfx.text(d, (12, y), f"{clip(text, 23)} {age_str(ts)}", small=True)
            y += 10
