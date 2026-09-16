"""ScreensaverPage — idle animation with clock and sleeping mascots.

Activates only after 90 s of no button input AND no system activity. It is
a rest screen: it must never hide work in progress. Any button press, or any
real activity (agents running, a download, heavy CPU, a fresh event) wakes
the panel and returns it to the working view.

The screensaver renders at only 2 FPS to keep CPU usage low while idle.
"""
import time

from .base import Page
from ..util.constants import W


class ScreensaverPage(Page):
    """Idle screensaver with clock and sleeping mascot."""

    IDLE_TIMEOUT = 90.0      # seconds of no input AND no activity
    CLOCK_FORMAT_12 = True   # 12h vs 24h clock

    name = "Screensaver"

    def __init__(self):
        self.last_input = time.time()
        self.last_activity = 0.0
        self._phase = 0.0

    def feed_input(self, now):
        """Call when any button is pressed to reset the idle timer."""
        self.last_input = now

    def feed_activity(self, now):
        """Call while the machine or the agents are working.

        Activity keeps the screensaver away so the panel shows the work in
        progress instead of the clock.
        """
        self.last_activity = now

    def idle_seconds(self, now=None):
        """Seconds since the last button press or activity, whichever is later."""
        now = now if now is not None else time.time()
        return now - max(self.last_input, self.last_activity)

    def should_show(self, now=None, busy=False):
        """Whether the screensaver should be active.

        Never while *busy*: if something is being done the panel must show it.
        """
        if busy:
            return False
        return self.idle_seconds(now) > self.IDLE_TIMEOUT

    def render(self, gfx, d, st, oc, dl, ctx):
        now = time.time()
        self._phase += 0.05  # slow animation

        mascot = ctx.get("mascot")
        mood = "idle"  # sleeping is shown via low-FPS bob, not a separate mood

        # Draw sleeping mascot on the left (gentle bob at 2 FPS)
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

        # Separator line
        d.line([(58, 1), (58, 41)], fill=255)

        # Clock on the right side
        t = time.localtime()
        if self.CLOCK_FORMAT_12:
            h = t.tm_hour % 12 or 12
            period = "AM" if t.tm_hour < 12 else "PM"
            time_str = f"{h}:{t.tm_min:02d}"
            gfx.text(d, (64, 8), time_str)
            gfx.text(d, (64, 22), period, small=True)
        else:
            time_str = f"{t.tm_hour}:{t.tm_min:02d}"
            gfx.text(d, (64, 10), time_str)

        # Date below
        date_str = f"{t.tm_mday}/{t.tm_mon}"
        gfx.text(d, (64, 32), date_str, small=True)

        # Breathing indicator (subtle brightness pulse on the line)
        breath = 0.5 + 0.5 * (0.5 + 0.5 * (now % 4.0 / 4.0 * 6.28))
        # In mono, we can't do brightness; instead, vary the dot pattern
        dot_x = 58
        dot_y = 21
        if int(now * 0.5) % 2 == 0:
            d.point((dot_x, dot_y), fill=255)

        # Page dots (smaller, dimmer)
        gfx.page_dots(d)
