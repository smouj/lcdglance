"""StatusPage — B3 scouter with power level animation.

Layout (160x43):
  Header: SCOUTER // ANALYSIS + PL number (animates up from 0)
  Row 1: CPU bar + temp
  Row 2: RAM bar + GW status dot
  Row 3: DSK bar + AG count + CODEX status
  
Power level animates from 0 to the actual value over ~300ms when
the scouter opens, mimicking the Dragon Ball scouter effect.
"""
import math
import time

from .base import Page
from ..util.constants import W, H
from ..util.text import clip, age_str


class StatusPage(Page):
    name = "Status"
    _opened_at = 0.0  # class-level: when the scouter was activated

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        load = ctx.get("load", 0)
        now = time.time()

        # Animate power level: ramp from 0 to actual over 300ms
        if self._opened_at == 0:
            self._opened_at = now
        elapsed = now - self._opened_at
        anim_duration = 0.3
        if elapsed < anim_duration:
            progress = elapsed / anim_duration
            # Ease-out: fast start, slow end
            progress = 1.0 - (1.0 - progress) ** 2
            pl_display = int(load * progress)
        else:
            pl_display = load

        # Header with power level
        gfx.frame(d, "SCOUTER", f"PL {pl_display:,}")

        y = 13
        # Row 1: CPU + temp
        cpu_pct = st.get("cpu", 0)
        gfx.text(d, (3, y), f"CPU {cpu_pct:3.0f}%", small=True)
        bar_x = 55
        bar_w = 72
        gfx.hbar(d, bar_x, y + 1, bar_w, 8, cpu_pct / 100.0)
        # CPU sparkline overlay
        buf = ctx.get("hist_bufs", {}).get("cpu")
        if buf and len(buf) >= 3:
            gfx.sparkline(d, bar_x, y + 1, bar_w, 8, buf)

        temps = st.get("temps", [])
        temp_str = self._best_temp(temps)
        gfx.text(d, (130, y), temp_str, small=True)
        y += 10

        # Row 2: RAM + GW dot
        ram_pct = st.get("mem", 0)
        gfx.text(d, (3, y), f"RAM {ram_pct:3.0f}%", small=True)
        gfx.hbar(d, bar_x, y + 1, bar_w, 8, ram_pct / 100.0)
        buf = ctx.get("hist_bufs", {}).get("ram")
        if buf and len(buf) >= 3:
            gfx.sparkline(d, bar_x, y + 1, bar_w, 8, buf)

        # Gateway status dot
        state = s.get("state", "offline")
        if state == "online":
            d.ellipse([143, y + 1, 149, y + 7], fill=255)
            gw_text = "UP"
        elif state == "stale":
            d.ellipse([143, y + 1, 149, y + 7], outline=255)
            d.line([(144, y + 4), (148, y + 4)], fill=255)  # dash = stale
            gw_text = "STALE"
        else:
            d.line([(143, y + 1), (149, y + 7)], fill=255)
            d.line([(143, y + 7), (149, y + 1)], fill=255)
            gw_text = "DOWN"
        gfx.text(d, (152, y), gw_text, small=True)
        y += 10

        # Row 3: DSK + AG + CODEX
        disk_pct = st.get("disk", 0)
        agents_count = sum((s.get("active_agents") or {}).values())
        gfx.text(d, (3, y), f"DSK {disk_pct:3.0f}%", small=True)
        gfx.hbar(d, bar_x, y + 1, bar_w, 8, disk_pct / 100.0)

        # Agent count
        ag_str = f"AG{agents_count}" if agents_count else "AG0"
        gfx.text(d, (130, y), ag_str, small=True)
        y += 10

        # Row 4: CODEX + supervisor info
        if s.get("codex_active"):
            codex = "CODEX * active"
        elif s.get("codex_mtime"):
            codex = f"CODEX {age_str(s['codex_mtime'])}"
        else:
            codex = "CODEX n/a"
        gfx.text(d, (3, y), clip(codex, 25), small=True)

        # Supervisor state (small, right side)
        latency = s.get("latency", 0)
        if latency > 0:
            gfx.text(d, (120, y), f"{latency:.1f}s", small=True)

    @staticmethod
    def _best_temp(temps, default="--"):
        """Pick the best temperature reading."""
        if not temps:
            return default
        for label, value in temps:
            low = label.lower()
            if "core" in low or "cpu" in low or "package" in low or "tctl" in low:
                return f"{value:.0f}C"
        return f"{temps[0][1]:.0f}C"

    @classmethod
    def reset_animation(cls):
        """Reset the power level animation (call when scouter opens)."""
        cls._opened_at = 0.0
