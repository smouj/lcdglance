"""ButtonHandler — detects taps, holds, and combos on the G510's four LCD buttons.

B1 = previous page            (tap)  / jump to the first page        (hold)
B2 = next page                (tap)  / jump to the last page         (hold)
B3 = cycle the mascot         (tap)  / scouter readout               (hold)
B4 = flash + toggle RGB alert (tap) / flash + push the ALERT state   (hold)
B1+B2 = jump forward three pages
B3+B4 = open the quick menu

Timing contract (this is what the README documents):

  * a tap fires on RELEASE, and only if the button came up before
    HOLD_THRESHOLD — one press produces either a tap or a hold, never both;
  * a hold fires once, while the button is still down, at HOLD_THRESHOLD;
  * a combo fires when the second button of the pair goes down within
    CHORD_WINDOW of the first, and swallows both individual taps;
  * a hold never fires while its combo partner is also down.

Waiting for the release is what makes a hold unambiguous. The previous
press-edge version emitted 'status_tap' instantly, so a 600 ms press produced
'status_tap' *and* 'status_hold'. The chord window fixes the mirror problem:
B1+B2 only registered when both bits appeared in the same 20 ms poll, so a
finger landing 40 ms late was read as two separate page changes.
"""
from ..util.constants import BTN_1, BTN_2, BTN_3, BTN_4


class ButtonHandler:
    """Debounced button input with release-edge taps, holds and chords."""

    BITS = (BTN_1, BTN_2, BTN_3, BTN_4)

    HOLD_THRESHOLD = 0.5    # seconds down before a press becomes a hold
    CHORD_WINDOW = 0.10     # the pair must land within this to be a chord
    DEBOUNCE = 0.03         # contact-bounce guard after a release

    TAP = {BTN_1: "prev", BTN_2: "next",
           BTN_3: "status_tap", BTN_4: "flash_tap"}
    HOLD = {BTN_1: "first_page", BTN_2: "last_page",
            BTN_3: "status_hold", BTN_4: "flash_hold"}
    PAIRS = ((BTN_1, BTN_2, "combo_12"), (BTN_3, BTN_4, "combo_34"))

    def __init__(self, lcd):
        self.lcd = lcd
        self.prev = 0
        self._press_ts = {}      # bit -> press timestamp
        self._last_release = {}  # bit -> release timestamp (bounce guard)
        self._hold_fired = set() # bits whose hold already fired this press
        self._chord_pairs = set()# pairs that fired a chord this press cycle
        self._chord_bits = set() # bits belonging to a fired chord (no tap/hold)

    # ─── helpers ────────────────────────────────────────────────────
    def _partner(self, bit):
        for a, b, _ in self.PAIRS:
            if bit == a:
                return b
            if bit == b:
                return a
        return 0

    def poll(self, now):
        """Poll buttons and return a list of (action, param) tuples.

        Actions: 'prev', 'next', 'first_page', 'last_page',
                 'status_tap', 'status_hold', 'flash_tap', 'flash_hold',
                 'combo_12', 'combo_34'
        """
        actions = []
        cur = 0
        for bit in self.BITS:
            if self.lcd.button(bit):
                cur |= bit

        new = cur & ~self.prev
        released = self.prev & ~cur
        self.prev = cur

        # 1 — press edges (with a bounce guard). A press never acts here:
        #     taps wait for the release, holds wait for HOLD_THRESHOLD.
        for bit in self.BITS:
            if not (new & bit):
                continue
            if (now - self._last_release.get(bit, 0.0)) < self.DEBOUNCE:
                continue
            self._press_ts[bit] = now
            self._hold_fired.discard(bit)
            self._chord_bits.discard(bit)

        # 2 — chords: the partner must land inside CHORD_WINDOW
        for a, b, action in self.PAIRS:
            if (a, b) in self._chord_pairs:
                continue
            if not (cur & a and cur & b):
                continue
            ta, tb = self._press_ts.get(a), self._press_ts.get(b)
            if ta is None or tb is None or abs(ta - tb) > self.CHORD_WINDOW:
                continue
            self._chord_pairs.add((a, b))
            self._chord_bits.update((a, b))
            self._hold_fired.update((a, b))
            actions.append((action, None))

        # 3 — holds, once, while the button is still down
        for bit in self.BITS:
            if not (cur & bit) or bit in self._chord_bits:
                continue
            start = self._press_ts.get(bit)
            if start is None or bit in self._hold_fired:
                continue
            if (now - start) < self.HOLD_THRESHOLD:
                continue
            if cur & self._partner(bit):
                continue          # partner down: this is a chord attempt
            self._hold_fired.add(bit)
            actions.append((self.HOLD[bit], None))

        # 4 — releases: the tap, when it was neither a hold nor a chord
        for bit in self.BITS:
            if not (released & bit):
                continue
            self._last_release[bit] = now
            start = self._press_ts.pop(bit, None)
            held = bit in self._hold_fired
            chord = bit in self._chord_bits
            self._hold_fired.discard(bit)
            if start is None or held or chord:
                continue
            if (now - start) < self.HOLD_THRESHOLD:
                actions.append((self.TAP[bit], None))

        # 5 — re-arm chord pairs once both buttons are up
        for a, b, _ in self.PAIRS:
            if not (cur & a) and not (cur & b):
                self._chord_pairs.discard((a, b))
                self._chord_bits.difference_update((a, b))

        return actions
