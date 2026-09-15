"""RGB LED controller for whole-keyboard backlight via Logitech LED SDK."""
import ctypes
import time

from ..util.constants import LED_DLL_PATH


class LEDController:
    """Whole-keyboard RGB backlight via LogiLed* calls."""

    def __init__(self, dll_path=LED_DLL_PATH):
        self.dll_path = dll_path
        self.led = None
        self.connected = False
        self._hw_until = 0.0

    def connect(self):
        if not self.led and not os.path.exists(self.dll_path):
            print(f"[!] LED DLL missing: {self.dll_path}", flush=True)
            return False
        try:
            self.led = ctypes.CDLL(self.dll_path)
            if not self.led.LogiLedInit():
                print("[!] LED init failed", flush=True)
                self.led = None
                return False
            self.connected = True
            self.led.LogiLedSaveCurrentLighting()
            time.sleep(0.05)
            print("[OK] RGB LED connected", flush=True)
            return True
        except Exception as e:
            print(f"[!] LED error: {e}", flush=True)
            self.led = None
            return False

    def hw_busy(self):
        return time.time() < self._hw_until

    def set_color(self, color):
        if self.connected and self.led:
            try:
                self.led.LogiLedSetLighting(
                    ctypes.c_int(color[0]),
                    ctypes.c_int(color[1]),
                    ctypes.c_int(color[2]))
            except Exception:
                pass

    def flash_async(self, color, dur_ms=2000, interval_ms=220):
        if self.connected and self.led:
            try:
                self.led.LogiLedFlashLighting(
                    ctypes.c_int(color[0]),
                    ctypes.c_int(color[1]),
                    ctypes.c_int(color[2]),
                    ctypes.c_int(dur_ms),
                    ctypes.c_int(interval_ms))
                self._hw_until = time.time() + dur_ms / 1000.0 + 0.1
            except Exception:
                pass

    def stop_effects(self):
        if self.connected and self.led:
            try:
                self.led.LogiLedStopEffects()
            except Exception:
                pass
        self._hw_until = 0.0

    def shutdown(self):
        if self.connected and self.led:
            try:
                self.led.LogiLedStopEffects()
                self.led.LogiLedRestoreLighting()
                self.led.LogiLedShutdown()
            except Exception:
                pass
        self.connected = False
        self.led = None


import os  # needed for path check above
