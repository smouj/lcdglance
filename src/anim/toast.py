"""ToastManager — lightweight notification overlay that appears at the top of the LCD.

Toasts slide in from above, hold for a configurable duration, then fade out.
They render ON TOP of the current page without replacing it, so brief events
(agent finished, download started) don't need a full page switch.
"""
import time

from ..util.constants import W
from ..util.text import clip, ascii_text


class ToastManager:
    """Manages a queue of short notification toasts on the LCD."""

    def __init__(self):
        self.queue = []          # [(text, severity, until)]
        self._current = None    # (text, severity, appear_time)
        self._fade_until = 0.0
        self._dedup = {}         # (text, severity) -> timestamp of last push

    def push(self, text, severity="info", duration=2.0):
        """Add a toast notification.

        severity: "info", "ok", "warn", "error"
        duration: seconds to display before fading

        Duplicate pushes (same text+severity within 3s) are silently dropped
        to prevent the same event from queuing dozens of identical toasts.
        """
        now = time.time()
        key = (text, severity)
        if key in self._dedup and now - self._dedup[key] < 3.0:
            return  # dedup: same toast within 3 seconds
        self._dedup[key] = now
        self.queue.append((text, severity, now + duration))
        # If nothing is showing, start immediately
        if self._current is None:
            self._advance(now)

    def _advance(self, now):
        """Pop the next toast from the queue."""
        # Expire old entries
        self.queue = [(t, s, u) for t, s, u in self.queue if u > now]
        # Prune dedup entries older than 10 seconds
        self._dedup = {k: v for k, v in self._dedup.items() if now - v < 10.0}
        if self.queue:
            text, severity, until = self.queue.pop(0)
            self._current = (text, severity, now)
            self._fade_until = until
        else:
            self._current = None
            self._fade_until = 0.0

    def render(self, d, gfx, now):
        """If a toast is active, render an overlay bar at the top of the LCD.

        Returns True if a toast was rendered (caller should skip title overlap).
        """
        if self._current is None:
            self._advance(now)

        if self._current is None:
            return False

        text, severity, appear = self._current
        remaining = self._fade_until - now

        # Toast expired?
        if remaining <= 0:
            self._current = None
            self._advance(now)
            return False

        # Draw a 10px bar at the top with the toast text
        # Background: filled white bar
        d.rectangle([0, 0, W - 1, 10], fill=255)
        # Severity icon
        icon_x = 2
        if severity == "ok":
            # Checkmark
            d.line([(icon_x, 5), (icon_x + 2, 8)], fill=0)
            d.line([(icon_x + 2, 8), (icon_x + 6, 2)], fill=0)
            icon_x += 8
        elif severity == "error" or severity == "warn":
            # Exclamation
            d.rectangle([icon_x + 2, 2, icon_x + 4, 6], fill=0)
            d.rectangle([icon_x + 2, 8, icon_x + 4, 9], fill=0)
            icon_x += 8
        else:
            icon_x += 2

        # Text in inverse (black on white)
        gfx.text(d, (icon_x, 0), clip(text, 28), small=True)

        # Fade-out effect: last 0.3s, render every other frame
        if remaining < 0.3 and int(now * 8) % 2 == 0:
            # Redraw as blank (blink effect for fade-out)
            d.rectangle([0, 0, W - 1, 10], fill=0)
            return True

        return True

    @property
    def active(self):
        return self._current is not None and time.time() < self._fade_until
