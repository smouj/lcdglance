"""LCD panel controller for the Logitech G510 mono 160×43 display.

Handles init, reconnection, bitmap submission, and button polling
via the Logitech LCD SDK DLL. The mono background buffer is ONE BYTE
PER PIXEL (6880 bytes), not a packed 1-bpp bitmap — passing 860
bytes makes the SDK read past the end and renders noise.
"""
import ctypes
import os
import time

from ..supervisor import ConnectionSupervisor

from ..util.constants import (
    W, H, BITMAP_SIZE, LOGI_LCD_TYPE_MONO,
    BTN_1, BTN_2, BTN_3, BTN_4, LCD_DLL_PATH,
)


class LCDController:
    """Thin wrapper around LogitechLcd.dll for the mono LCD."""

    def __init__(self, dll_path=LCD_DLL_PATH):
        self.dll_path = dll_path
        self.lcd = None
        self.connected = False
        self._last_connect = 0.0
        self._buf = None
        self.sup = ConnectionSupervisor("lcd")

    def connect(self):
        if not os.path.exists(self.dll_path):
            print(f"[!] LCD DLL missing: {self.dll_path}", flush=True)
            return False
        try:
            self.lcd = ctypes.CDLL(self.dll_path)
            if not self.lcd.LogiLcdInit(ctypes.c_wchar_p("LCDGlance"),
                                        LOGI_LCD_TYPE_MONO):
                print("[!] LCD init failed", flush=True)
                self.lcd = None
                return False
            self.connected = True
            self._last_connect = time.time()
            time.sleep(0.1)
            print("[OK] LCD connected", flush=True)
            return True
        except Exception as e:
            print(f"[!] LCD error: {e}", flush=True)
            self.lcd = None
            return False

    def ensure_connected(self, now=None):
        import time as _t
        now = now or _t.time()
        if self.connected and self.lcd:
            try:
                if self.lcd.LogiLcdIsConnected(LOGI_LCD_TYPE_MONO):
                    self.sup.mark_online()
                    return True
            except Exception:
                pass
        # Health check failed or never connected — try reconnect if backoff allows
        if self.sup.should_reconnect(now):
            self.sup.mark_connecting()
            self.shutdown()
            result = self.connect()
            if not result:
                self.sup.next_backoff()
            return result
        return self.connected

    def button(self, bit):
        """Poll one button (BTN_1..BTN_4)."""
        if not (self.connected and self.lcd):
            return False
        try:
            return bool(self.lcd.LogiLcdIsButtonPressed(bit))
        except Exception:
            return False

    def buttons(self):
        """Return a bitmask of all pressed buttons."""
        mask = 0
        for bit in (BTN_1, BTN_2, BTN_3, BTN_4):
            if self.button(bit):
                mask |= bit
        return mask

    def submit(self, data):
        """Send an already-converted mono buffer (6880 bytes) to the panel."""
        if not (self.connected and self.lcd):
            return
        try:
            self._buf = ctypes.create_string_buffer(data, len(data))
            self.lcd.LogiLcdMonoSetBackground(self._buf)
            self.lcd.LogiLcdUpdate()
        except Exception:
            pass

    def update(self):
        """Re-submit the last frame (no data change, just refresh)."""
        if self.connected and self.lcd:
            try:
                self.lcd.LogiLcdUpdate()
            except Exception:
                pass

    def health(self):
        """Return supervisor snapshot for diagnostics."""
        return self.sup.snapshot()

    def shutdown(self):
        if self.connected and self.lcd:
            try:
                self.lcd.LogiLcdShutdown()
            except Exception:
                pass
        self.connected = False
        self.lcd = None
