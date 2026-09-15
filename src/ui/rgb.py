"""RGBEngine — whole-keyboard RGB ambient backlight driven by page and state."""
import math
import time

from ..util.constants import (
    LOAD_PALETTE, PAGE_THEME, MASCOT_COLOR, ACTIVE_COLOR, RGB_STATE,
)


def lerp_palette(pal, v):
    """Interpolate a colour from a palette at value v in [0, 1]."""
    if v <= pal[0][0]:
        return pal[0][1]
    if v >= pal[-1][0]:
        return pal[-1][1]
    for i in range(len(pal) - 1):
        v0, c0 = pal[i]
        v1, c1 = pal[i + 1]
        if v0 <= v <= v1:
            f = 0.0 if v1 == v0 else (v - v0) / (v1 - v0)
            return tuple(int(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
    return pal[-1][1]


class RGBEngine:
    def __init__(self, led, oc, dl, vps=None):
        self.led = led
        self.oc = oc
        self.dl = dl
        self.vps = vps
        self.manual_alert = False
        self.active_source_key = "openclaw"
        self.busy = False
        self._seen_event_ts = 0.0

    @staticmethod
    def _breath(period):
        t = time.time()
        return 0.55 + 0.45 * (0.5 + 0.5 * math.sin(2 * math.pi * t / period))

    @staticmethod
    def _night():
        h = time.localtime().tm_hour
        return 0.35 if (h >= 23 or h < 8) else 1.0

    @staticmethod
    def _scale(c, f):
        return tuple(max(0, min(100, int(v * f))) for v in c)

    def _ambient(self, st, page):
        if page == 0:
            if getattr(self, "busy", False):
                return ACTIVE_COLOR
            return MASCOT_COLOR.get(self.active_source_key, (0, 80, 95))
        if page == 2:
            return lerp_palette(LOAD_PALETTE, st.get("cpu", 0) / 100.0)
        if page == 7:
            vps = self.vps.snapshot() if hasattr(self, 'vps') and self.vps else {}
            if vps.get("online"):
                return (0, 70, 80)
            return (80, 20, 20)
        return PAGE_THEME.get(page) or (0, 60, 90)

    def update(self, st, page):
        if not self.led.connected:
            RGB_STATE["effect"] = "off"
            return
        now = time.time()
        oc = self.oc.snapshot()

        if self.manual_alert:
            if not self.led.hw_busy():
                self.led.set_color(self._scale((100, 0, 0), self._breath(1.1)))
            RGB_STATE["effect"] = "ALERT red"
            return

        ev = oc.get("last_event")
        if ev and (now - ev["ts"] < 6) and ev["ts"] != self._seen_event_ts:
            self._seen_event_ts = ev["ts"]
            if ev["kind"] == "ok":
                self.led.flash_async((0, 100, 20), 2200, 220)
                RGB_STATE["effect"] = "AGENT DONE"
            else:
                self.led.flash_async((100, 0, 0), 2600, 160)
                RGB_STATE["effect"] = "AGENT FAIL"
            return

        if self.led.hw_busy():
            return

        if self.dl.active:
            self.led.set_color(self._scale((0, 60, 100), self._breath(2.0) * self._night()))
            RGB_STATE["effect"] = "DOWNLOAD"
            return

        if oc.get("running", 0) > 0:
            self.led.set_color(self._scale((0, 85, 100), self._breath(1.6) * self._night()))
            RGB_STATE["effect"] = "AGENTS"
            return

        cpu, mem, dsk = st.get("cpu", 0), st.get("mem", 0), st.get("disk", 0)
        if cpu > 90:
            self.led.set_color(self._scale((100, 45, 0), self._breath(0.9)))
            RGB_STATE["effect"] = "CPU HIGH"
            return
        if mem > 90:
            self.led.set_color(self._scale((100, 100, 0), self._breath(0.9)))
            RGB_STATE["effect"] = "RAM HIGH"
            return
        if dsk > 95:
            self.led.set_color(self._scale((100, 0, 0), self._breath(1.8)))
            RGB_STATE["effect"] = "DISK FULL"
            return

        base = self._ambient(st, page)
        self.led.set_color(self._scale(base, self._breath(3.2) * self._night()))
        names = {0: "mascot", 1: "sources", 2: "cpu-load", 3: "network",
                 4: "procs", 5: "openclaw", 6: "alerts", 7: "vps"}
        RGB_STATE["effect"] = names.get(page, "ambient")

    def sweep(self):
        if not self.led.connected:
            return
        for c in [(80, 0, 0), (80, 40, 0), (80, 80, 0), (0, 80, 0),
                  (0, 80, 80), (0, 0, 80), (60, 0, 80)]:
            self.led.set_color(c)
            time.sleep(0.07)
        self.led.set_color((0, 0, 0))
