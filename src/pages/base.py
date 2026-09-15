"""Base Page class and shared drawing helpers."""
import time

from ..util.constants import W, H
from ..util.text import ascii_text, clip, age_str, fmt_speed, fmt_bytes, fmt_uptime


class Page:
    """Base class for all LCD pages."""
    name = "Page"

    def render(self, gfx, d, st, oc, dl, ctx):
        pass


def _alert_icon(d, x, y, kind):
    """Small severity glyph: bang for failures, tick for successes, dot for info."""
    if kind == "fail":
        d.rectangle([x + 2, y, x + 3, y + 5], fill=255)
        d.rectangle([x + 2, y + 7, x + 3, y + 8], fill=255)
    elif kind == "ok":
        d.line([(x, y + 5), (x + 3, y + 8)], fill=255)
        d.line([(x + 3, y + 8), (x + 7, y + 1)], fill=255)
    else:
        d.rectangle([x + 2, y + 3, x + 4, y + 5], fill=255)
