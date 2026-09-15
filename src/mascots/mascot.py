"""MascotRenderer — three hand-drawn 1-bit mascots with blinking, bobbing and idle glances.

Each mascot (CLAW crab, CODEX robot, PC monitor) is rendered procedurally
using Pillow draw primitives. The MascotRenderer handles blink timing,
look direction, and bob offset internally.

In v9, the MascotRenderer also checks for sprite data from the sprite
module. If a sprite set exists for the current key+mood, it is blitted
directly; otherwise, the procedural fallback is used.
"""
import math
import time

from ..render.bitmap import to_mono_bytes
from ..util.constants import W


class MascotRenderer:
    """Three hand-drawn 1-bit mascots with blinking, bobbing and idle glances."""

    def __init__(self, gfx, sprites=None):
        self.gfx = gfx
        self.sprites = sprites  # SpriteSet or None (procedural only)
        self._blink_next = time.time() + 3.0
        self._blink_until = 0.0
        self._look = 0
        self._look_next = time.time() + 4.0

    def _anim(self):
        """Compute blink state and look direction for the current tick."""
        now = time.time()
        blinking = now < self._blink_until
        if now > self._blink_next:
            self._blink_until = now + 0.12
            self._blink_next = now + 2.2 + (hash(int(now)) % 30) / 10.0
            blinking = True
        if now > self._look_next:
            self._look = (-2, 0, 2)[hash(int(now)) % 3]
            self._look_next = now + 2.5 + (hash(int(now * 7)) % 25) / 10.0
        bob = int(round(1.4 * math.sin(now * 2.3)))
        return blinking, bob

    def _activity_flare(self, d, cx, cy):
        """Energy flares bursting sideways from the mascot while it is busy."""
        for dx, dy in ((-18, -6), (-18, 3), (18, -6), (18, 3),
                       (-12, -13), (12, -13)):
            d.line([(cx + dx, cy + dy),
                    (cx + int(dx * 1.55), cy + int(dy * 1.35 + (2 if dy > 0 else -2)))],
                   fill=255)

    def draw(self, d, key, cx, cy, mood, busy=False):
        """Draw the mascot for *key* at (cx, cy) with the given *mood*."""
        # Try sprite rendering first
        if self.sprites and self.sprites.has(key, mood):
            self.sprites.blit(d, key, mood, cx, cy, busy=busy)
            return

        # Procedural fallback
        blinking, bob = self._anim()
        cy += bob
        if busy:
            self._activity_flare(d, cx, cy)
        if key == "openclaw":
            self._claw(d, cx, cy, mood, blinking)
        elif key == "codex":
            self._codex(d, cx, cy, mood, blinking)
        else:
            self._pc(d, cx, cy, mood, blinking)

    def _eyes(self, d, cx, cy, gap, r, blinking):
        if blinking:
            d.line([(cx - gap - r, cy), (cx - gap + r, cy)], fill=255)
            d.line([(cx + gap - r, cy), (cx + gap + r, cy)], fill=255)
            return
        for ex in (cx - gap, cx + gap):
            d.ellipse([ex - r, cy - r, ex + r, cy + r], outline=255)
            lx = self._look
            d.ellipse([ex + lx - 1, cy - 1, ex + lx + 1, cy + 1], fill=255)

    def _mouth(self, d, cx, cy, mood):
        if mood == "happy":
            d.arc([cx - 6, cy - 5, cx + 6, cy + 4], 20, 160, fill=255)
        elif mood == "alarm":
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline=255)
        elif mood == "worried":
            d.line([(cx - 5, cy + 1), (cx + 5, cy + 1)], fill=255)
        else:
            d.line([(cx - 4, cy), (cx + 4, cy)], fill=255)

    def _claw(self, d, cx, cy, mood, blinking):
        """OpenClaw: a little crab."""
        d.rounded_rectangle([cx - 15, cy - 10, cx + 15, cy + 11],
                            radius=8, outline=255)
        spread = 3 if mood in ("watch", "happy", "focus") else 0
        d.arc([cx - 25 - spread, cy - 12, cx - 13 + spread, cy + 2], 90, 280, fill=255)
        d.arc([cx + 13 - spread, cy - 12, cx + 25 + spread, cy + 2], 260, 90, fill=255)
        for dy in (-5, 0, 5):
            d.line([(cx - 15, cy + dy), (cx - 21, cy + dy + 3)], fill=255)
            d.line([(cx + 15, cy + dy), (cx + 21, cy + dy + 3)], fill=255)
        ey = cy - 16
        d.line([(cx - 7, cy - 10), (cx - 7, ey + 3)], fill=255)
        d.line([(cx + 7, cy - 10), (cx + 7, ey + 3)], fill=255)
        self._eyes(d, cx, ey, 7, 3, blinking)
        self._mouth(d, cx, cy + 5, mood)

    def _codex(self, d, cx, cy, mood, blinking):
        """Codex: a robot with a scanning visor."""
        d.rounded_rectangle([cx - 15, cy - 12, cx + 15, cy + 13],
                            radius=4, outline=255)
        d.line([(cx, cy - 12), (cx, cy - 17)], fill=255)
        if int(time.time() * 2) % 2 == 0:
            d.ellipse([cx - 2, cy - 20, cx + 2, cy - 16], fill=255)
        else:
            d.ellipse([cx - 2, cy - 20, cx + 2, cy - 16], outline=255)
        vx0, vx1, vy0, vy1 = cx - 11, cx + 11, cy - 7, cy + 1
        d.rectangle([vx0, vy0, vx1, vy1], outline=255)
        if blinking:
            d.line([(vx0 + 1, (vy0 + vy1) // 2), (vx1 - 1, (vy0 + vy1) // 2)], fill=255)
        else:
            span = (vx1 - vx0) - 8
            px = vx0 + 1 + int(span * (0.5 + 0.5 * math.sin(time.time() * 1.7)))
            d.rectangle([px, vy0 + 1, px + 5, vy1 - 1], fill=255)
        for row in range(2):
            for col in range(4):
                x = cx - 9 + col * 5
                y = cy + 5 + row * 4
                filled = (mood == "happy") or ((row * 4 + col) % 3 != 2)
                if filled:
                    d.rectangle([x, y, x + 2, y + 2], fill=255)
                else:
                    d.rectangle([x, y, x + 2, y + 2], outline=255)

    def _pc(self, d, cx, cy, mood, blinking):
        """Your PC: a monitor with a face."""
        d.rounded_rectangle([cx - 16, cy - 13, cx + 16, cy + 7],
                            radius=3, outline=255)
        d.line([(cx, cy + 7), (cx, cy + 12)], fill=255)
        d.line([(cx - 7, cy + 12), (cx + 7, cy + 12)], fill=255)
        self._eyes(d, cx, cy - 5, 8, 3, blinking)
        self._mouth(d, cx, cy + 2, mood)

    # ---- mini versions for the sources strip
    def draw_mini(self, d, key, cx, cy, busy):
        if key == "openclaw":
            d.ellipse([cx - 8, cy - 5, cx + 8, cy + 6], outline=255)
            d.arc([cx - 14, cy - 6, cx - 7, cy + 2], 100, 270, fill=255)
            d.arc([cx + 7, cy - 6, cx + 14, cy + 2], 270, 80, fill=255)
            d.line([(cx - 4, cy - 5), (cx - 4, cy - 8)], fill=255)
            d.line([(cx + 4, cy - 5), (cx + 4, cy - 8)], fill=255)
            d.ellipse([cx - 5, cy - 10, cx - 3, cy - 8], fill=255)
            d.ellipse([cx + 3, cy - 10, cx + 5, cy - 8], fill=255)
        elif key == "codex":
            d.rounded_rectangle([cx - 8, cy - 6, cx + 8, cy + 6],
                                radius=2, outline=255)
            d.line([(cx, cy - 6), (cx, cy - 9)], fill=255)
            if busy:
                d.rectangle([cx - 5, cy - 2, cx + 5, cy + 1], fill=255)
            else:
                d.rectangle([cx - 5, cy - 2, cx + 5, cy + 1], outline=255)
        else:
            d.rounded_rectangle([cx - 8, cy - 7, cx + 8, cy + 4],
                                radius=2, outline=255)
            d.line([(cx, cy + 4), (cx, cy + 7)], fill=255)
            d.line([(cx - 4, cy + 7), (cx + 4, cy + 7)], fill=255)
            d.ellipse([cx - 4, cy - 3, cx - 2, cy - 1], fill=255)
            d.ellipse([cx + 2, cy - 3, cx + 4, cy - 1], fill=255)
