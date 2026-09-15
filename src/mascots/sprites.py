"""Sprite-based mascot rendering for the G510 LCD.

Each mascot sprite is stored as a list of row strings where '#' is a lit pixel
and '.' is dark. The SpriteSet converts these to bytes on demand and caches
them. Sprites are blitted directly onto the PIL draw surface — no binarisation.

OPT-IN: this renderer is disabled by default (constants.USE_SPRITES = False).
The hand-drawn procedural mascots in mascot.py read better on the real 1-bit
panel, where pixel-art sprites alias badly at ~30px. When enabled, SpriteSet
takes precedence and MascotRenderer falls back to procedural for any key+mood
that has no sprite. Sprite data is hand-designed for the 160x43 LCD.
"""
import time

from ..util.constants import W, H


class SpriteSet:
    """Manages sprite data for all mascots and their moods.

    Sprites are stored as dict of (key, mood) → {"rows": [...], "anchor": (cx, cy)}.
    The rows are lists of strings using '#' for lit pixels and '.' for dark.
    Width is derived from the longest row; height from the number of rows.
    """

    def __init__(self):
        self._cache = {}   # (key, mood) → pre-rasterised pixel list [(x, y)]

    def add(self, key, mood, rows, anchor=None):
        """Add a sprite from ASCII art rows.

        Args:
            key: "openclaw", "codex", or "pc"
            mood: "idle", "watch", "happy", "worried", "alarm", "focus"
            rows: list of strings, '#' = lit, '.' = dark
            anchor: (cx, cy) center point, defaults to centre of bounding box
        """
        # Collect lit pixels
        pixels = []
        max_w = max(len(r) for r in rows) if rows else 0
        h = len(rows)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == '#':
                    pixels.append((x, y))
        if anchor is None:
            anchor = (max_w // 2, h // 2)
        self._cache[(key, mood)] = {
            "pixels": pixels,
            "anchor": anchor,
        }

    def has(self, key, mood):
        """Check if a sprite exists for the given key+mood."""
        return (key, mood) in self._cache

    def blit(self, d, key, mood, cx, cy, busy=False):
        """Blit the sprite centered at (cx, cy) onto a PIL ImageDraw.

        Args:
            d: PIL ImageDraw object
            key: mascot key
            mood: expression mood
            cx, cy: center position
            busy: if True, add activity flares

        Returns:
            True if sprite was found and blitted, False otherwise
        """
        sprite = self._cache.get((key, mood))
        if sprite is None:
            return False

        ax, ay = sprite["anchor"]
        pixels = sprite["pixels"]
        x0 = cx - ax
        y0 = cy - ay

        for px, py in pixels:
            dx = x0 + px
            dy = y0 + py
            if 0 <= dx < W and 0 <= dy < H:
                d.point((dx, dy), fill=255)

        # Activity flares for busy state
        if busy:
            self._draw_flares(d, cx, cy)

        return True

    def _draw_flares(self, d, cx, cy):
        """Draw energy flares around the mascot."""
        for dx, dy in ((-18, -6), (-18, 3), (18, -6), (18, 3),
                       (-12, -13), (12, -13)):
            d.line([(cx + dx, cy + dy),
                    (cx + int(dx * 1.55), cy + int(dy * 1.35 + (2 if dy > 0 else -2)))],
                   fill=255)


# ─── OpenClaw (crab) sprites ──────────────────────────────────────
# Designed for ~28px wide × 28px tall at the left side of the panel
# The crab: rounded shell, eye stalks with pupils, claws, legs

_CLAW_IDLE = [
    "..........##..........",
    ".........####.........",
    ".........####.........",
    "..##....######....##..",
    "..##....######....##..",
    "...##....####....##...",
    "........########......",
    ".......##########.....",
    "......############....",
    ".....##############...",
    "......############....",
    "......####..####.......",
    ".......##..##..........",
    "......###..###.........",
    ".....###....###........",
    "......###..###.........",
    ".......##..##..........",
    "......####..####.......",
    ".....####....####......",
    "....####......####.....",
    "...###..........###...",
    "...##............##....",
    "...##............##....",
    "...#..............#....",
    "...##............##...",
    "....##..........##....",
    ".....###........##.....",
    "......####....###......",
]

_CLAW_WATCH = [
    "..........##..........",
    ".........####.........",
    ".........####.........",
    "..##....######...##...",
    "..##....######...##...",
    "...##....####....##...",
    "........########......",
    ".......##########.....",
    "......############....",
    ".....##############...",
    "....################...",
    "......####...####.......",
    ".....###.....###........",
    "....###.......###.......",
    "...###.........##.......",
    "....###.......###.......",
    ".....##.......##........",
    "....####.....####.......",
    "...####.......####......",
    "..####.........####.....",
    "..###..........###.....",
    "..##............##......",
    "..##............##......",
    "..#..............#......",
    "..##............##.....",
    "...##..........##......",
    "....###........##.......",
    ".....####......###......",
]

_CLAW_HAPPY = [
    "..........##..........",
    ".........####.........",
    ".........####.........",
    "..##....######...##...",
    "..##....######...##...",
    "...##....####....##...",
    "........########......",
    ".......##########.....",
    "......############....",
    ".....##############...",
    "....################...",
    "......####...####.......",
    ".....###.####.###.......",
    "....###.........##......",
    "...###..........###.....",
    "....###.........##......",
    ".....##..####...##.......",
    "....####.......####......",
    "...####.........####.....",
    "..####...........####....",
    "..###.............###....",
    "..##...............##....",
    "..##...............##....",
    "..#.................#....",
    "..##...............##...",
    "...##.............##....",
    "....###..........##.....",
    ".....####.......###......",
]

_CLAW_ALARM = [
    "..........##..........",
    ".........####.........",
    ".........####.........",
    "..##....######...##...",
    "..##....######...##...",
    "...##....####....##...",
    "........########......",
    ".......##########.....",
    "......############....",
    ".....##############...",
    "....################...",
    "......####...####.......",
    ".....###......###.......",
    "....###........###......",
    "...###..........###.....",
    "....###........###......",
    ".....##........##.......",
    "....####......####.......",
    "...####........####......",
    "..####..........####.....",
    "..###............###....",
    "..##..............##....",
    "..##..............##....",
    "..#................#.....",
    "..##..............##...",
    "...##............##....",
    "....###..........##.....",
    ".....####........###.....",
]

# ─── Codex (robot) sprites ────────────────────────────────────────

_CODEX_IDLE = [
    ".....#....................",
    ".....##...................",
    "....####..................",
    "...######.................",
    "...#.##.##................",
    "..##.##.###...............",
    "..###.##.####..............",
    ".#####.##.#####.............",
    "..###..##.####..............",
    "...##..##..###...............",
    "...##..##..##...............",
    "...####..####...............",
    "...####...####..............",
    "...####..#####..............",
    "...###.....####.............",
    "...##.......###.............",
    "....#.........##............",
    "...##..........##..........",
    "..###..........###.........",
    "...##............##.........",
    "..###............###........",
    "...##..............##........",
    "..###..............###.......",
    "...##................##.......",
    "..............................",
    "..............................",
    "..............................",
    "..............................",
]

# ─── PC (monitor) sprites ─────────────────────────────────────────

_PC_IDLE = [
    "......##############.......",
    ".....################......",
    "....##################.....",
    "...####################....",
    "...####..........####......",
    "...####..##..##...####.....",
    "...####..##..##...####.....",
    "...####..........####.....",
    "...####..####....####......",
    "...####..........####......",
    "....################.......",
    ".....################.......",
    ".........####...............",
    ".........####...............",
    ".........####...............",
    "......########..............",
    ".....########...............",
    "..............................",
    "..............................",
    "..............................",
    "..............................",
    "..............................",
    "..............................",
    "..............................",
    "..............................",
    "..............................",
    "..............................",
    "..............................",
]


def create_default_sprites():
    """Create the default sprite set with all mascot moods."""
    sprites = SpriteSet()

    # OpenClaw (crab) - all moods
    sprites.add("openclaw", "idle", _CLAW_IDLE)
    sprites.add("openclaw", "watch", _CLAW_WATCH)
    sprites.add("openclaw", "happy", _CLAW_HAPPY)
    sprites.add("openclaw", "alarm", _CLAW_ALARM)
    sprites.add("openclaw", "worried", _CLAW_IDLE)   # reuse idle, expression via mouth
    sprites.add("openclaw", "focus", _CLAW_WATCH)     # reuse watch with flares

    # Codex (robot) - idle only for now; procedural fallback for others
    sprites.add("codex", "idle", _CODEX_IDLE)

    # PC (monitor) - idle only for now; procedural fallback for others
    sprites.add("pc", "idle", _PC_IDLE)

    return sprites
