"""ScreensaverPage — idle animation with clock and sleeping mascots.

Activates after 90-120 seconds of no button input. Shows a slowly
breathing mascot (at 2 FPS) with the current time, cycling through
a subtle animation. Any button press returns to the previous page.

The screensaver reduces CPU usage by rendering at only 2 FPS and
skipping all data collection when idle.
"""
import time

from .base import Page
from ..util.constants import W


class ScreensaverPage(Page):
    """Idle screensaver with clock and sleeping mascot."""

    IDLE_TIMEOUT = 90.0     # seconds without input before screensaver
    DIM_TIMEOUT = 60.0       # seconds before partial dim
    CLOCK_FORMAT_12 = True   # 12h vs 24h clock

    name = "Screensaver"

    def __init__(self):
        self.last_input = time.time()
        self._phase = 0.0

    def feed_input(self, now):
        """Call when any button is pressed to reset the idle timer."""
        self.last_input = now

    @property
    def should_show(self):
        """Whether the screensaver should be active."""
        return time.time() - self.last_input > self.IDLE_TIMEOUT

    @property
    def is_dimming(self):
        """Whether we should start dimming (partial idle)."""
        return time.time() - self.last_input > self.DIM_TIMEOUT

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
