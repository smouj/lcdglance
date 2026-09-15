"""QuickMenuPage — context-sensitive menu activated by button combos.

B3+B4 (hold both): opens the quick menu
B1: previous option
B2: next option
B3: select current option
B4: cancel / close menu

Options are dynamic based on current context:
  - Network: toggle DNS, flush cache
  - OpenClaw: restart gateway, poll now
  - System: task manager
  - VPS: reconnect
  - Display: toggle screensaver
"""
import time

from .base import Page
from ..util.text import clip, ascii_text


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
        self.items.append(("Net Reset", "net_reset", "Reset network adapter"))

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

        # Show 3 items at a time, with the selected one highlighted
        visible_start = max(0, self.selected - 1)
        visible_end = min(n_items, visible_start + 3)

        y = 13
        for i in range(visible_start, visible_end):
            name, action, desc = self.items[i]
            is_sel = (i == self.selected)

            if is_sel:
                # Highlight: filled bar behind the text
                d.rectangle([0, y, W - 1, y + 9], fill=255)
                gfx.text(d, (3, y), clip(f"> {name}", 24), small=True)
            else:
                gfx.text(d, (5, y), clip(name, 24), small=True)
            y += 10

        # Description of selected item at bottom
        if self.items and 0 <= self.selected < len(self.items):
            _, _, desc = self.items[self.selected]
            gfx.text(d, (3, 36), clip(desc, 30), small=True)
