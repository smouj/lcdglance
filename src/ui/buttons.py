"""ButtonHandler — detects taps, holds, and combos on the G510's four LCD buttons.

B1/B2 = prev/next page
B3 = scouter overlay (tap) / refresh OpenClaw (hold)
B4 = screen flash (tap) / toggle manual RGB alert (hold)
B1+B2 = cycle pages quickly
B3+B4 = reserved (future: screensaver toggle)

Hold detection: a button held for >0.5s triggers the hold action.
Combos: simultaneous press of two buttons within 150ms.
"""
import time

from ..util.constants import BTN_1, BTN_2, BTN_3, BTN_4


class ButtonHandler:
    """Debounced button input with hold and combo detection."""

    HOLD_THRESHOLD = 0.5   # seconds to register a hold
    DEBOUNCE = 0.12        # minimum gap between distinct presses

    def __init__(self, lcd):
        self.lcd = lcd
        self.prev = 0
        self._last_ts = 0.0
        self._hold_start = {}   # bit -> timestamp
        self._hold_fired = set()  # bits that already fired hold

    def poll(self, now):
        """Poll buttons and return a list of (action, param) tuples.

        Actions: 'prev', 'next', 'status_tap', 'status_hold',
                 'flash_tap', 'flash_hold', 'combo_12', 'combo_34'
        """
        actions = []
        cur = 0
        for bit in (BTN_1, BTN_2, BTN_3, BTN_4):
            if self.lcd.button(bit):
                cur |= bit

        new = cur & ~self.prev
        released = self.prev & ~cur
        self.prev = cur

        # Check for holds on sustained presses
        for bit in (BTN_1, BTN_2, BTN_3, BTN_4):
            if cur & bit:
                start = self._hold_start.get(bit)
                if start and (now - start) >= self.HOLD_THRESHOLD and bit not in self._hold_fired:
                    self._hold_fired.add(bit)
                    if bit == BTN_3:
                        actions.append(("status_hold", None))
                    elif bit == BTN_4:
                        actions.append(("flash_hold", None))
            if released & bit:
                self._hold_start.pop(bit, None)
                self._hold_fired.discard(bit)

        if not new:
            return actions

        if (now - self._last_ts) < self.DEBOUNCE:
            return actions

        # Track hold starts for new presses
        for bit in (BTN_1, BTN_2, BTN_3, BTN_4):
            if new & bit:
                self._hold_start[bit] = now

        # Detect combos first
        if new & BTN_1 and new & BTN_2:
            actions.append(("combo_12", None))
            self._last_ts = now
            return actions
        if new & BTN_3 and new & BTN_4:
            actions.append(("combo_34", None))
            self._last_ts = now
            return actions

        # Detect taps (only if hold hasn't fired)
        for bit, action in ((BTN_1, "prev"), (BTN_2, "next"),
                            (BTN_3, "status_tap"), (BTN_4, "flash_tap")):
            if new & bit and bit not in self._hold_fired:
                actions.append((action, None))

        self._last_ts = now
        return actions
