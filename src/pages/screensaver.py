"""ScreensaverPage — idle animation with clock, sleeping mascot, and
periodic system-nominal interlude.

Activates only after 90 s of no button input AND no system activity.
Never hides work in progress. Every 12 seconds, briefly shows system
status (CPU/RAM) before returning to the sleeping mascot.
"""
import time

from .base import Page
from ..util.constants import W
from ..util.text import fmt_speed


class ScreensaverPage(Page):
    """Idle screensaver with clock, sleeping mascot, and status interlude."""

    IDLE_TIMEOUT = 90.0
    INTERLUDE_EVERY = 12.0   # seconds between system-nominal flashes
    INTERLUDE_DURATION = 2.5  # how long the interlude lasts

    name = "Screensaver"

    def __init__(self):
        self.last_input = time.time()
        self.last_activity = 0.0
        self._phase = 0.0

    def feed_input(self, now):
        self.last_input = now

    def feed_activity(self, now):
        self.last_activity = now

    def idle_seconds(self, now=None):
        now = now if now is not None else time.time()
        return now - max(self.last_input, self.last_activity)

    def should_show(self, now=None, busy=False):
        if busy:
            return False
        return self.idle_seconds(now) > self.IDLE_TIMEOUT

    def render(self, gfx, d, st, oc, dl, ctx):
        now = time.time()
        self._phase += 0.05
        mascot = ctx.get("mascot")

        # Decide: show mascot+clock or system-nominal interlude
        idle_time = self.idle_seconds(now)
        cycle_pos = idle_time % self.INTERLUDE_EVERY
        show_interlude = cycle_pos > (self.INTERLUDE_EVERY - self.INTERLUDE_DURATION)

        if show_interlude:
            self._render_interlude(gfx, d, st, oc, dl, now)
        else:
            self._render_mascot(gfx, d, st, mascot, now)

    def _render_mascot(self, gfx, d, st, mascot, now):
        """Sleeping mascot with clock and zzz."""
        bob = int(round(0.7 * (1.0 + 1.0 * (now % 3.0 - 1.5) / 1.5)))
        if mascot:
            mascot.draw(d, "openclaw", 30, 20 + bob, "idle", busy=False)
            # Zzz floating above
            phase = int(now * 0.5) % 3
            for i, (dx, dy) in enumerate([(0, 0), (4, -5), (8, -10)]):
                if i <= phase:
                    zx, zy = 44 + dx, 8 + dy
                    d.point((zx, zy), fill=255)
                    d.point((zx + 1, zy), fill=255)

        # Separator
        d.line([(58, 1), (58, 41)], fill=255)

        # Clock
        t = time.localtime()
        h = t.tm_hour % 12 or 12
        period = "AM" if t.tm_hour < 12 else "PM"
        gfx.text(d, (64, 8), f"{h}:{t.tm_min:02d}")
        gfx.text(d, (64, 22), period, small=True)

        # Date
        days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        day_str = days[t.tm_wday]
        gfx.text(d, (64, 32), f"{day_str} {t.tm_mday}/{t.tm_mon}", small=True)

        # Breathing dot
        if int(now * 0.5) % 2 == 0:
            d.point((58, 21), fill=255)

        gfx.page_dots(d)

    def _render_interlude(self, gfx, d, st, oc, dl, now):
        """System nominal flash: CPU/RAM/NET summary."""
        gfx.frame(d, "NOMINAL", "")

        y = 13
        cpu = st.get("cpu", 0)
        mem = st.get("mem", 0)
        dn = st.get("net_dn", 0)

        # Checkmark icon
        cx, cy = 80, 20
        d.line([(cx - 6, cy), (cx - 2, cy + 4)], fill=255)
        d.line([(cx - 2, cy + 4), (cx + 6, cy - 5)], fill=255)

        gfx.text(d, (3, y), f"CPU {cpu:3.0f}%  RAM {mem:3.0f}%", small=True)
        y += 10
        gfx.text(d, (3, y), f"DN {fmt_speed(dn)}", small=True)
        y += 10

        s = oc.snapshot()
        if s.get("online"):
            running = s.get("running", 0)
            if running:
                gfx.text(d, (3, y), f"AGENTS {running} running", small=True)
            else:
                gfx.text(d, (3, y), "all quiet", small=True)
        else:
            gfx.text(d, (3, y), "gateway offline", small=True)
