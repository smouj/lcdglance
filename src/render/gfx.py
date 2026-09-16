"""Graphics toolkit for drawing on a 160x43 1-bit canvas.

Provides: text, bars, sparklines, page chrome (title + clock + dots + rule),
and the canvas factory. Uses Pillow for text rendering with a LUT-based
binarisation pass (never dithering).

Font hierarchy:
  - Consolas Bold 11px for titles
  - Consolas Bold 10px for body text
  - PIL default as ultimate fallback
"""
import os
import time

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from ..util.constants import W, H
from ..util.text import ascii_text, clip


class Gfx:
    """Small drawing helpers on a 160x43 1-bit canvas."""

    def __init__(self):
        self.font = None
        self.font_small = None
        self.dots = None          # (index, total) page indicator, set per frame
        if HAS_PIL:
            for cand in ("consolab.ttf", "consola.ttf", "lucon.ttf"):
                p = os.path.join(r"C:\Windows\Fonts", cand)
                if os.path.exists(p):
                    try:
                        self.font = ImageFont.truetype(p, 11)
                        self.font_small = ImageFont.truetype(p, 10)
                        break
                    except Exception:
                        pass
            if self.font is None:
                self.font = ImageFont.load_default()
            if self.font_small is None:
                self.font_small = self.font

    def page_dots(self, d, dots=None):
        """Page indicator dots pinned to top-right."""
        dots = dots if dots is not None else self.dots
        if not dots:
            return
        idx, total = dots
        bx = W - 4 - ((total - 1) * 3 + 3)
        for i in range(total):
            cx = bx + i * 3
            if i == idx:
                d.rectangle([cx, 4, cx + 2, 6], fill=255)
            else:
                d.point((cx + 1, 5), fill=255)

    def _clock_str(self):
        """Return HH:MM clock string for the current time."""
        t = time.localtime()
        return f"{t.tm_hour:2d}:{t.tm_min:02d}"

    def frame(self, d, title, right="", dots=None, clock=True):
        """Shared page chrome: title, clock, right context, rule, page dots.

        Layout (160px wide, 12px header band):
          [4px] TITLE ... [gap] ... HH:MM [gap] ... dots [4px]
        The clock sits right-aligned in the space between title and dots,
        with a 6px gap before the dots and a 6px gap after the title.
        'right' text (e.g. uptime) is placed between title and clock.
        """
        dots = dots if dots is not None else self.dots
        total = dots[1] if dots else 0

        # --- Title (left-aligned at x=4) ---
        t = ascii_text(title)
        d.text((4, -1), t, font=self.font, fill=255)
        tw = int(d.textlength(t, font=self.font))

        # --- Horizontal rule ---
        d.line([(0, 12), (W - 1, 12)], fill=255)

        # --- Page dots (right-aligned, top-right corner) ---
        self.page_dots(d, dots)

        # --- Calculate the left edge of the dots block ---
        if total:
            dots_left = W - 6 - ((total - 1) * 3 + 3)
        else:
            dots_left = W - 2
        dots_left = min(dots_left, W - 4)

        # --- Right zone: gap between title end and dots start ---
        # Title ends at tw+4 (4px left margin + title width)
        title_end = tw + 4
        # Available space for clock + right text: from title_end+6 to dots_left-6
        zone_left = title_end + 6
        zone_right = dots_left - 6

        # --- Clock (small font, in the right zone) ---
        # The clock is placed right-aligned within the zone,
        # so it sits just left of the dots with a clean gap.
        if clock:
            clk = self._clock_str()
            clk_w = int(d.textlength(clk, font=self.font_small))
            clk_x = zone_right - clk_w
            # Never overlap the title: minimum 6px gap
            if clk_x < title_end + 6:
                clk_x = title_end + 6
            d.text((clk_x, 1), clk, font=self.font_small, fill=255)

        # --- Right text (e.g. uptime) — placed between title and clock ---
        if right:
            r = ascii_text(right)
            rw = int(d.textlength(r, font=self.font_small))
            if clock:
                # Place right text just left of the clock
                clk = self._clock_str()
                clk_w = int(d.textlength(clk, font=self.font_small))
                rx = zone_right - clk_w - 6 - rw
            else:
                rx = zone_right - rw
            if rx > title_end + 6:
                d.text((rx, 0), r, font=self.font_small, fill=255)

    @staticmethod
    def canvas():
        img = Image.new("L", (W, H), 0)
        return img, ImageDraw.Draw(img)

    def text(self, d, xy, s, small=False, fill=255):
        """Draw *s* at *xy*. fill=0 renders inverse (black on a white bar)."""
        d.text(xy, ascii_text(s), font=(self.font_small if small else self.font), fill=fill)

    @staticmethod
    def hline(d, y, x0=0, x1=W - 1):
        d.line([(x0, y), (x1, y)], fill=255)

    @staticmethod
    def hbar(d, x, y, w, h, pct, fill=255, outline=True):
        pct = max(0.0, min(1.0, pct))
        if outline:
            d.rectangle([x, y, x + w - 1, y + h - 1], outline=fill)
            inner_w = max(0, int((w - 2) * pct))
            if inner_w > 0:
                d.rectangle([x + 1, y + 1, x + inner_w, y + h - 2], fill=fill)
        else:
            inner_w = max(0, int(w * pct))
            if inner_w:
                d.rectangle([x, y, x + inner_w - 1, y + h - 1], fill=fill)

    @staticmethod
    def stripes(d, x, y, w, h, phase):
        """Indeterminate progress bar: moving blocks."""
        blk = 8
        off = int(phase) % (blk * 2)
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=255)
        xx = x + 1 - off
        while xx < x + w - 1:
            x0 = max(xx, x + 1)
            x1 = min(xx + blk - 1, x + w - 2)
            if x1 >= x0:
                d.rectangle([x0, y + 1, x1, y + h - 2], fill=255)
            xx += blk * 2

    @staticmethod
    def sparkline(d, x, y, w, h, values):
        if not values:
            return
        vals = values[-w:]
        mx = max(vals) or 1.0
        n = len(vals)
        pts = []
        for i, v in enumerate(vals):
            px = x + int(i * (w - 1) / max(1, n - 1))
            py = y + h - 1 - int((v / mx) * (h - 1))
            pts.append((px, py))
        if len(pts) > 1:
            d.line(pts, fill=255)
