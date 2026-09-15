"""Mascot interactions — clips where two mascots appear together on the LCD.

When two sources are simultaneously active (e.g. OpenClaw launches a task
to Codex), the MascotPage can show both characters in a shared scene instead
of just one. This module provides the interaction definitions and a renderer
that composes two mascots side by side or interacting.

Each interaction has:
  - keys: which two mascots participate (ordered pair)
  - trigger: what event triggers this interaction
  - duration: how long the interaction plays (seconds)
  - render: a function that draws both mascots on the canvas

For now, the renderers use the procedural MascotRenderer to draw both
characters in a composed scene. When sprite data is available for both
mascots, the SpriteSet handles blitting; this module just positions them.
"""
import time

from ..util.constants import W, H


class Interaction:
    """A two-mascot interaction scene."""

    def __init__(self, key_a, key_b, trigger, duration, render_fn):
        self.key_a = key_a      # e.g. "openclaw"
        self.key_b = key_b      # e.g. "codex"
        self.trigger = trigger  # "launch", "working", "success", "failure"
        self.duration = duration
        self.render_fn = render_fn

    def matches(self, sources):
        """Check if both mascots in this interaction are active."""
        keys = {s["key"] for s in sources if s.get("busy") or s.get("online")}
        return self.key_a in keys and self.key_b in keys


def _draw_launch(d, gfx, mascot, key_a, key_b, mood, frame):
    """CLAW launches a task to CODEX: CLAW on left reaching right, CODEX on right receiving."""
    # CLAW (left, reaching)
    mascot.draw(d, key_a, 40, 20, "watch", busy=True)
    # CODEX (right, receiving)
    mascot.draw(d, key_b, 120, 20, "focus", busy=False)
    # Connecting line (task beam)
    phase = int(time.time() * 8) % 3
    for i in range(phase):
        y = 18 + i * 3
        d.line([(55, y), (105, y)], fill=255)


def _draw_working(d, gfx, mascot, key_a, key_b, mood, frame):
    """Both mascots looking at a shared task in the middle."""
    mascot.draw(d, key_a, 40, 22, "watch", busy=False)
    mascot.draw(d, key_b, 120, 22, "watch", busy=False)
    # Shared progress indicator in center
    pct = 0.5 + 0.5 * abs((time.time() % 4.0) - 2.0) / 2.0
    gfx.hbar(d, 65, 28, 30, 5, pct)


def _draw_success(d, gfx, mascot, key_a, key_b, mood, frame):
    """Both mascots celebrating — CLAW happy, CODEX happy."""
    mascot.draw(d, key_a, 40, 20, "happy", busy=False)
    mascot.draw(d, key_b, 120, 20, "happy", busy=False)
    # Celebration sparkles
    t = time.time()
    for i in range(5):
        angle = t * 3 + i * 1.256
        sx = int(80 + 15 * (1 if i % 2 == 0 else -1) + 8 * (i % 3 - 1))
        sy = int(12 + (i * 4) % 16)
        d.point((sx, sy), fill=255)


def _draw_failure(d, gfx, mascot, key_a, key_b, mood, frame):
    """Both mascots concerned — CLAW worried, CODEX alarmed."""
    mascot.draw(d, key_a, 40, 20, "worried", busy=False)
    mascot.draw(d, key_b, 120, 20, "alarm", busy=True)
    # Error indicator
    d.rectangle([75, 30, 85, 38], outline=255)
    d.line([(77, 32), (83, 36)], fill=255)
    d.line([(77, 36), (83, 32)], fill=255)


# ─── Interaction registry ──────────────────────────────────────────
# Ordered by priority: first match wins

INTERACTIONS = [
    Interaction("openclaw", "codex", "launch",   4.0, _draw_launch),
    Interaction("openclaw", "codex", "working",   6.0, _draw_working),
    Interaction("openclaw", "codex", "success",   3.0, _draw_success),
    Interaction("openclaw", "codex", "failure",   4.0, _draw_failure),
    # PC + OpenClaw: PC busy while CLAW works
    Interaction("pc", "openclaw", "working",   5.0, _draw_working),
    # PC + Codex: PC hosting CODEX work
    Interaction("pc", "codex", "working",     5.0, _draw_working),
]


def find_interaction(sources, trigger=None):
    """Find the best matching interaction for current sources.

    Args:
        sources: list of source dicts with "key", "busy", "online"
        trigger: optional event trigger ("launch", "success", "failure")

    Returns:
        Interaction or None if no match
    """
    for inter in INTERACTIONS:
        if trigger and inter.trigger != trigger:
            continue
        if inter.matches(sources):
            return inter
    return None
