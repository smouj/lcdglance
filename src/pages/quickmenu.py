"""QuickMenuPage — context-sensitive menu activated by button combos.

B3+B4 (hold both): opens the quick menu
B1: previous option
B2: next option
B3: select current option
B4: cancel / close menu

Options are dynamic based on current context, including a Diagnostics
entry that shows connection supervisor states for LCD, RGB, OpenClaw, VPS.
"""
import time

from .base import Page
from ..util.constants import W
from ..util.text import clip, ascii_text, age_str


class QuickMenuPage(Page):
    """Context-sensitive quick menu page."""

    name = "QuickMenu"

    def __init__(self):
        self.items = []
        self.selected = 0
        self._built = False

    def build_menu(self, st, oc, dl, vps):
        """Build the menu items based on current context."""
        self.items = []
        s = oc.snapshot()

        # Always-available items
        self.items.append(("Poll Now", "poll", "Force an OpenClaw poll"))
        if s.get("online"):
            self.items.append(("Restart GW", "restart_gw", "Restart OpenClaw gateway"))
        self.items.append(("Task Mgr", "taskmgr", "Open Task Manager"))
        if vps and vps.enabled:
            if vps.snapshot().get("online"):
                self.items.append(("VPS Reconn", "vps_reconnect", "Force VPS re-poll"))
            else:
                self.items.append(("VPS Retry", "vps_retry", "Retry VPS connection"))

        # Network items
        self.items.append(("DNS Flush", "dns_flush", "Flush DNS cache"))

        # Diagnostics
        self.items.append(("Diagnostics", "diagnostics", "Show connection states"))

        # Display items
        self.items.append(("Screensaver", "screensaver", "Toggle screensaver mode"))

        self.selected = min(self.selected, max(0, len(self.items) - 1))
        self._built = True

    def select(self):
        """Return the action string of the currently selected item."""
        if 0 <= self.selected < len(self.items):
            return self.items[self.selected][1]
        return None

    def next_item(self):
        if self.items:
            self.selected = (self.selected + 1) % len(self.items)

    def prev_item(self):
        if self.items:
            self.selected = (self.selected - 1) % len(self.items)

    def render(self, gfx, d, st, oc, dl, ctx):
        if not self._built:
            self.build_menu(st, oc, dl, ctx.get("vps_snapshot", {}))

        n_items = len(self.items)
        gfx.frame(d, "MENU", f"{self.selected + 1}/{n_items}")

        # Show 3 items at a time, selected highlighted
        visible_start = max(0, self.selected - 1)
        visible_end = min(n_items, visible_start + 3)

        y = 13
        for i in range(visible_start, visible_end):
            name, action, desc = self.items[i]
            is_sel = (i == self.selected)

            if is_sel:
                d.rectangle([0, y, W - 1, y + 9], fill=255)
                gfx.text(d, (3, y), clip(f"> {name}", 24), small=True)
            else:
                gfx.text(d, (5, y), clip(name, 24), small=True)
            y += 10

        # Description of selected item at bottom
        if self.items and 0 <= self.selected < len(self.items):
            _, _, desc = self.items[self.selected]
            gfx.text(d, (3, 36), clip(desc, 30), small=True)


class DiagnosticsPage(Page):
    """Show connection supervisor states for LCD, RGB, OpenClaw, VPS."""
    name = "Diagnostics"

    def render(self, gfx, d, st, oc, dl, ctx):
        gfx.frame(d, "DIAGNOSTICS", "connections")

        y = 13
        # Gather health from supervisors
        components = []

        # LCD
        try:
            lcd_health = ctx.get("lcd_health", {})
            if lcd_health:
                state = lcd_health.get("state", "?")
                age = lcd_health.get("state_age", "?")
                components.append(("LCD", state, age))
            else:
                components.append(("LCD", "n/a", ""))
        except Exception:
            components.append(("LCD", "err", ""))

        # RGB
        try:
            rgb_health = ctx.get("rgb_health", {})
            if rgb_health:
                state = rgb_health.get("state", "?")
                age = rgb_health.get("state_age", "?")
                components.append(("RGB", state, age))
            else:
                components.append(("RGB", "n/a", ""))
        except Exception:
            components.append(("RGB", "err", ""))

        # OpenClaw
        s = oc.snapshot()
        oc_state = s.get("state", s.get("online") and "online" or "offline")
        oc_age = s.get("state_age", "")
        oc_latency = s.get("latency", 0)
        lat_str = f" {oc_latency:.1f}s" if oc_latency > 0 else ""
        components.append(("CLAW", oc_state, f"{oc_age}{lat_str}"))

        # VPS (if enabled)
        vps_snap = ctx.get("vps_snapshot", {})
        if vps_snap and vps_snap.get("enabled"):
            vps_state = vps_snap.get("state", vps_snap.get("online") and "online" or "offline")
            components.append(("VPS", vps_state, vps_snap.get("state_age", "")))

        for name, state, detail in components[:4]:
            # State icon
            if state == "online":
                d.ellipse([4, y + 1, 10, y + 7], fill=255)
            elif state == "stale":
                d.rectangle([4, y + 1, 10, y + 7], outline=255)
            elif state == "connecting":
                d.rectangle([4, y + 1, 10, y + 7], fill=255)
            else:
                d.line([(4, y + 1), (10, y + 7)], fill=255)
                d.line([(4, y + 7), (10, y + 1)], fill=255)

            gfx.text(d, (14, y), f"{name} {state}", small=True)
            if detail:
                gfx.text(d, (80, y), clip(detail, 16), small=True)
            y += 10

        # Fail counts
        y = min(y, 36)
        fail_count = s.get("fail_count", 0)
        if fail_count > 0:
            gfx.text(d, (3, y), f"OC fails: {fail_count}", small=True)
