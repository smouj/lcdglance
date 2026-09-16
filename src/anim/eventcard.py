"""EventCardManager — hardware-style notification cards.

Unlike toasts (a thin bar at the top), an event card takes over the whole
160×43 panel for ~2.5 s to announce something worth interrupting for:
an agent finishing, a build passing, a download completing.

Card layout:
    ───────────────────────────────
     ✓ CODEX
    ───────────────────────────────
      BUILD COMPLETE
      138 TESTS PASSED

                  20:18
    ───────────────────────────────

Only one card shows at a time; newer cards replace older ones.
"""
import time

from ..util.constants import W, H
from ..util.text import clip


class EventCardManager:
    """Full-panel notification cards with an icon, title and detail lines."""

    DURATION = 2.5   # seconds a card stays on screen

    def __init__(self):
        self._card = None      # (icon, title, lines, appear_ts)
        self._until = 0.0

    def push(self, icon, title, lines, duration=None):
        """Show a card. *lines* is a list of up to 2 detail strings.

        icon:  "ok" | "fail" | "down" | "info"
        """
        now = time.time()
        dur = duration if duration is not None else self.DURATION
        self._card = (icon, title, list(lines)[:2], now)
        self._until = now + dur

    @property
    def active(self):
        return self._card is not None and time.time() < self._until

    def clear(self):
        self._card = None
        self._until = 0.0

    def render(self, d, gfx, now):
        """Render the active card. Returns True if a card was drawn."""
        if not self.active:
            if self._card is not None:
                self.clear()
            return False

        icon, title, lines, _ = self._card

        # Big centred title row, inverse
        d.rectangle([0, 11, W - 1, 22], fill=255)

        # Icon glyph on the left of the title bar (drawn in inverse = black)
        self._icon(d, 4, 14, icon)

        # Title after the icon (inverse: black on the white bar)
        gfx.text(d, (18, 13), clip(title, 22), small=True, fill=0)

        # Detail lines below the bar
        y = 25
        for line in lines:
            gfx.text(d, (6, y), clip(line, 26), small=True)
            y += 10

        # Clock bottom-right
        t = time.localtime()
        clock = f"{t.tm_hour:02d}:{t.tm_min:02d}"
        w = int(d.textlength(clock, font=gfx.font_small))
        gfx.text(d, (W - 4 - w, 33), clock, small=True)

        return True

    @staticmethod
    def _icon(d, x, y, kind):
        """Draw the card icon in inverse (black strokes on white)."""
        if kind == "ok":
            d.line([(x, y + 4), (x + 3, y + 7)], fill=0)
            d.line([(x + 3, y + 7), (x + 8, y)], fill=0)
        elif kind == "fail":
            d.rectangle([x + 2, y, x + 4, y + 5], fill=0)
            d.rectangle([x + 2, y + 7, x + 4, y + 9], fill=0)
        elif kind == "down":
            d.line([(x + 4, y), (x + 4, y + 7)], fill=0)
            d.line([(x, y + 3), (x + 4, y + 7)], fill=0)
            d.line([(x + 8, y + 3), (x + 4, y + 7)], fill=0)
        else:
            d.rectangle([x + 2, y + 3, x + 5, y + 6], fill=0)
