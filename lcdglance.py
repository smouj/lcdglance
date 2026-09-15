#!/usr/bin/env python3
"""
LCDGlance v7.1 — Logitech G510 (160x43 mono LCD), bitmap graphics edition.

LCD is rendered as real graphics with Pillow (not just text):
  - Agent face with expressions (idle / watching / happy / worried / alarm)
  - Progress bars, sparklines, separators
  - Smart auto-focus: shows the Download view while a download is running,
    the face with a reaction when an agent finishes, then returns to your page.

Pages (B1/B2):
  1 Face      agent avatar + status
  2 System    CPU / RAM / disk bars
  3 Network   up/down speed + sparkline
  4 Procs     top processes
  5 OpenClaw  subagent counts + last job
  6 Alerts    system + agent alerts
  7 VPS       remote server SSH stats (if configured)
  * Download  appears automatically while downloading

RGB (whole-keyboard, LGS 8.57 LED SDK):
  page-themed ambient + breathing, warnings, agent flashes, night dimming.
"""

import ctypes
import io
import json
import math
import os
import subprocess
import threading
import traceback
import time

# ─── Configuration ───────────────────────────────────────────────

LGS_DIR = r"C:\Program Files\Logitech Gaming Software"
LCD_DLL = os.path.join(LGS_DIR, "SDK", "LCD", "x64", "LogitechLcd.dll")
LED_DLL = os.path.join(LGS_DIR, "SDK", "LED", "x64", "LogitechLed.dll")

LOGI_LCD_TYPE_MONO = 0x00000001
BTN_1, BTN_2, BTN_3, BTN_4 = 0x01, 0x02, 0x04, 0x08

W, H = 160, 43
# The mono background buffer is ONE BYTE PER PIXEL: 160*43 = 6880 bytes.
# Reference: logitech-lcd crate asserts `mono_bitmap.len() == MONO_WIDTH * MONO_HEIGHT`
# and documents "160x43 bytes". Passing a packed 1-bpp 860-byte buffer makes the
# SDK read ~6000 bytes past the end, which renders as noise on the LCD.
BITMAP_SIZE = W * H

UPDATE_INTERVAL = 0.25         # loop tick: keeps button polling responsive
ANIM_INTERVAL = 0.25           # mascot / download pages (bob, blink, stripes)
STATIC_INTERVAL = 0.8          # data pages: content barely changes
RESUBMIT_AFTER = 5.0           # re-send even if unchanged (protects against LGS)
LCD_CHECK_INTERVAL = 5.0
OC_POLL_INTERVAL = 15.0
DL_POLL_INTERVAL = 1.0

HERE = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(HERE, "oc_seen.json")
VPS_CONFIG_FILE = os.path.join(HERE, "vps_config.json")

# One WSL round-trip returns everything: subagent history (alerts + counts),
# currently running tasks (which source is active) and Codex activity.
# A helper script inside WSL does the heavy lifting (openclaw tasks --json over
# every runtime is ~1.6 MB of JSON) and prints only compact lines, so next to
# nothing crosses to Windows. See lcd-probe in this folder.
WSL_CMD = ["wsl.exe", "-d", "Ubuntu-24.04", "-e", "bash", "-lc", "lcd-probe"]
CREATE_NO_WINDOW = 0x08000000

TERMINAL_OK = {"succeeded"}
TERMINAL_BAD = {"failed", "timed_out", "cancelled", "lost"}

RGB_STATE = {"effect": "-"}

# bitmap rendering switches
INVERT = False        # True -> swap lit/unlit pixels

BIN_THRESHOLD = 120   # luminance cutoff when binarising anti-aliased text.
                      # 128 loses 'o','N','P' on regular Consolas; 100 merges the
                      # three strokes of a lowercase 'm' into a solid block.
                      # 120 + Consolas Bold 11 px keeps both whole glyphs and 'm'.

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


_TRANSLIT = {
    "·": "-", "•": "-", "—": "-", "–": "-", "…": "...", "°": "o",
    "á": "a", "à": "a", "ä": "a", "â": "a", "ã": "a",
    "é": "e", "è": "e", "ë": "e", "ê": "e",
    "í": "i", "ì": "i", "ï": "i", "î": "i",
    "ó": "o", "ò": "o", "ö": "o", "ô": "o", "õ": "o",
    "ú": "u", "ù": "u", "ü": "u", "û": "u",
    "ñ": "n", "ç": "c",
    "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N",
    "✓": "v", "✔": "v", "✗": "x", "✘": "x",
}


def ascii_text(text):
    out = []
    for ch in str(text):
        if 32 <= ord(ch) <= 126:
            out.append(ch)
        else:
            out.append(_TRANSLIT.get(ch, "?"))
    return "".join(out).replace("\n", " ").replace("\r", " ")


def clip(text, n):
    t = ascii_text(text)
    return t if len(t) <= n else t[: n - 1] + "\u2026".replace("\u2026", "~")


def fmt_speed(mbps):
    if mbps >= 10:
        return f"{mbps:.0f}MB/s"
    if mbps >= 1:
        return f"{mbps:.1f}MB/s"
    return f"{mbps * 1024:.0f}KB/s"


def fmt_bytes(mb):
    if mb >= 1024:
        return f"{mb / 1024:.2f}GB"
    if mb >= 1:
        return f"{mb:.1f}MB"
    return f"{mb * 1024:.0f}KB"


def fmt_uptime(sec):
    return f"{int(sec) // 3600}h{(int(sec) % 3600) // 60:02d}m"


def age_str(ts):
    d = int(time.time() - ts)
    if d < 60:
        return f"{d}s"
    if d < 3600:
        return f"{d // 60}m"
    return f"{d // 3600}h"


# ─── palettes / colour math ──────────────────────────────────────

LOAD_PALETTE = [
    (0.00, (5, 18, 70)), (0.30, (0, 70, 95)), (0.55, (10, 90, 45)),
    (0.75, (95, 70, 0)), (1.00, (100, 12, 12)),
]
PAGE_THEME = {
    0: None,              # Mascot   -> colour of the active source
    1: (70, 60, 90),      # Sources  -> slate
    2: None,              # System   -> CPU gradient
    3: (0, 65, 90),       # Network  -> teal
    4: (60, 25, 95),      # Procs    -> violet
    5: (0, 80, 95),       # OpenClaw -> cyan
    6: (95, 60, 0),       # Alerts   -> amber
    7: (0, 60, 80),       # VPS      -> dark teal
}


def lerp_palette(pal, v):
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


# subagent = a real agent run; cron = an automation; acp = Codex; cli = our own
# exec noise, which the probe filters out.
RUNTIME_TAG = {"subagent": "AGENT", "cron": "AUTO", "acp": "CODEX", "cli": "CLI"}


def _section(text, start_marker, end_marker):
    """Return the text between two markers (kept for ad-hoc debugging)."""
    i = text.find(start_marker)
    if i < 0:
        return ""
    i += len(start_marker)
    j = text.find(end_marker, i) if end_marker else -1
    return text[i:j] if j >= 0 else text[i:]


# ─── LGS applets that steal the LCD ──────────────────────────────

def kill_lcd_applets():
    for name in ("LCDMedia.exe", "LCDClock.exe", "LCDPop3.exe", "LCDRSS.exe",
                 "LCDYouTube.exe", "LCDCountdown.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/IM", name],
                           capture_output=True, timeout=3,
                           creationflags=CREATE_NO_WINDOW)
        except Exception:
            pass


_MONO_LUT = None


def _lut():
    """256-entry lookup table used to binarise the render in one C-level pass."""
    global _MONO_LUT
    if _MONO_LUT is None:
        if INVERT:
            _MONO_LUT = [0 if i >= BIN_THRESHOLD else 255 for i in range(256)]
        else:
            _MONO_LUT = [255 if i >= BIN_THRESHOLD else 0 for i in range(256)]
    return _MONO_LUT


def to_mono_bytes(img):
    """PIL image -> Logitech mono LCD background buffer (W*H bytes, one per pixel).

    Traps encoded here:
      * never use img.convert("1") — Pillow dithers by default (Floyd-Steinberg),
        turning crisp text into speckled noise. Threshold with a LUT instead.
      * the buffer is one BYTE per pixel (6880), not packed 1-bpp (860).
    """
    return img.convert("L").point(_lut()).tobytes()


def mono_to_image(data):
    """Round-trip the background buffer back to a PIL image (preview parity)."""
    img = Image.new("L", (W, H), 0)
    px = img.load()
    i = 0
    for y in range(H):
        for x in range(W):
            if data[i]:
                px[x, y] = 255
            i += 1
    return img


# ─── LCD controller (text + bitmap) ──────────────────────────────

class LCDController:
    def __init__(self, dll_path=LCD_DLL):
        self.dll_path = dll_path
        self.lcd = None
        self.connected = False
        self._last_connect = 0.0
        self._buf = None

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

    def ensure_connected(self):
        if self.connected and self.lcd:
            try:
                if self.lcd.LogiLcdIsConnected(LOGI_LCD_TYPE_MONO):
                    return True
            except Exception:
                pass
        if time.time() - self._last_connect < 2:
            return self.connected
        self.shutdown()
        return self.connect()

    def button(self, bit):
        if not (self.connected and self.lcd):
            return False
        try:
            return bool(self.lcd.LogiLcdIsButtonPressed(bit))
        except Exception:
            return False

    def set_text(self, line, text):
        if self.connected and self.lcd:
            try:
                self.lcd.LogiLcdMonoSetText(
                    ctypes.c_int(line), ctypes.c_wchar_p(clip(text, 40)))
            except Exception:
                pass

    def submit(self, data):
        """Send an already-converted mono buffer straight to the panel."""
        if not (self.connected and self.lcd):
            return
        try:
            # create_string_buffer, not (c_ubyte*n)(*data): the latter unpacks
            # 6880 Python ints into an argument list on every single frame.
            self._buf = ctypes.create_string_buffer(data, len(data))
            self.lcd.LogiLcdMonoSetBackground(self._buf)
            self.lcd.LogiLcdUpdate()
        except Exception:
            pass

    def set_bitmap(self, img):
        """img: PIL image 160x43 (any mode) -> mono bitmap, no dithering."""
        if not (self.connected and self.lcd):
            return
        try:
            data = to_mono_bytes(img)
            self._buf = ctypes.create_string_buffer(data, len(data))
            self.lcd.LogiLcdMonoSetBackground(self._buf)
        except Exception:
            pass

    def update(self):
        if self.connected and self.lcd:
            try:
                self.lcd.LogiLcdUpdate()
            except Exception:
                pass

    def shutdown(self):
        if self.connected and self.lcd:
            try:
                self.lcd.LogiLcdShutdown()
            except Exception:
                pass
        self.connected = False
        self.lcd = None


# ─── LED controller ──────────────────────────────────────────────

class LEDController:
    def __init__(self, dll_path=LED_DLL):
        self.dll_path = dll_path
        self.led = None
        self.connected = False
        self._hw_until = 0.0

    def connect(self):
        if not os.path.exists(self.dll_path):
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
                self.led.LogiLedSetLighting(ctypes.c_int(color[0]),
                                            ctypes.c_int(color[1]),
                                            ctypes.c_int(color[2]))
            except Exception:
                pass

    def flash_async(self, color, dur_ms=2000, interval_ms=220):
        if self.connected and self.led:
            try:
                self.led.LogiLedFlashLighting(
                    ctypes.c_int(color[0]), ctypes.c_int(color[1]),
                    ctypes.c_int(color[2]), ctypes.c_int(dur_ms),
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


# ─── RGB engine ──────────────────────────────────────────────────

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
                return ACTIVE_COLOR          # highlight colour while a source is busy
            return MASCOT_COLOR.get(self.active_source_key, (0, 80, 95))
        if page == 2:
            return lerp_palette(LOAD_PALETTE, st.get("cpu", 0) / 100.0)
        if page == 7:
            # VPS: teal when online, dim red when offline
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

        # downloading -> steady blue-cyan sweep feel
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


# ─── OpenClaw monitor ────────────────────────────────────────────

class OpenClawMonitor:
    def __init__(self):
        self._lock = threading.Lock()
        self.online = False
        self.running = self.ok = self.fail = self.total = 0
        self.last_task = ""
        self.last_task_status = ""
        self.last_poll_ok = 0.0
        self.alerts = []
        self.last_event = None
        self._seen = set()
        self._baselined = False
        self.active_agents = {}
        self.codex_seen = False
        self.codex_active = False
        self.codex_mtime = 0.0
        self.codex_last = ""
        self._load_seen()

    def _load_seen(self):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                self._seen = set(json.load(f).get("seen", []))
        except Exception:
            self._seen = set()

    def _save_seen(self):
        try:
            with open(SEEN_FILE, "w", encoding="utf-8") as f:
                json.dump({"seen": list(self._seen)[-500:]}, f)
        except Exception:
            pass

    def poll(self):
        """Read the compact lcd-probe lines and raise alerts for finished work."""
        try:
            r = subprocess.run(WSL_CMD, capture_output=True, timeout=180,
                               creationflags=CREATE_NO_WINDOW)
            out = r.stdout.decode("utf-8", errors="replace")
            now = time.time()
            new_alerts, new_events = [], []
            ok = fail = total = 0
            last_task = last_status = ""
            newest = -1
            active_agents = {}
            codex_mtime = 0.0
            codex_last = ""

            for line in out.splitlines():
                line = line.strip()
                if line.startswith("N|"):
                    try:
                        total = int(line[2:] or 0)
                    except ValueError:
                        pass
                elif line.startswith("R|"):
                    p = line.split("|", 2)
                    if len(p) >= 3:
                        a = p[2] or "?"
                        active_agents[a] = active_agents.get(a, 0) + 1
                elif line.startswith("T|"):
                    p = line.split("|", 6)
                    if len(p) < 7:
                        continue
                    _, tid, rt, st, agent, ended, label = p
                    if st in TERMINAL_OK:
                        ok += 1
                    elif st in TERMINAL_BAD:
                        fail += 1
                    try:
                        ended_i = int(ended or 0)
                    except ValueError:
                        ended_i = 0
                    if ended_i > newest:
                        newest, last_task, last_status = ended_i, label, st
                    fresh = bool(tid) and tid not in self._seen
                    if tid:
                        self._seen.add(tid)
                    if fresh and self._baselined:
                        good = st in TERMINAL_OK
                        kind = "ok" if good else "fail"
                        tag = RUNTIME_TAG.get(rt, (rt or "task").upper())
                        text = f"{tag} {'OK' if good else st.upper()}: {label}"
                        new_alerts.append((now, kind, text))
                        # flash + jump only for real agent runs and real problems;
                        # routine heartbeat successes would be noise.
                        if rt == "subagent" or not good:
                            new_events.append((now, kind, text))
                elif line.startswith("C2|"):
                    p = line.split("|", 2)
                    try:
                        codex_mtime = max(codex_mtime, float(p[1] or 0))
                    except (ValueError, IndexError):
                        pass
                    if len(p) >= 3:
                        codex_last = p[2]
                elif line.startswith("C|"):
                    try:
                        codex_mtime = max(codex_mtime, float(line[2:] or 0))
                    except ValueError:
                        pass

            self._save_seen()

            with self._lock:
                self.online = True
                self.running = sum(active_agents.values())
                self.ok, self.fail, self.total = ok, fail, total
                self.last_task, self.last_task_status = last_task, last_status
                self.last_poll_ok = now
                self.active_agents = active_agents
                self.codex_seen = codex_mtime > 0
                self.codex_mtime = codex_mtime
                self.codex_last = codex_last
                self.codex_active = bool(codex_mtime) and (now - codex_mtime) < 180
                if not self._baselined:
                    self._baselined = True
                    self.alerts.append((now, "info", "OpenClaw link up"))
                for ts, kind, text in new_alerts:
                    self.alerts.append((ts, kind, text))
                for ts, kind, text in new_events:
                    self.last_event = {"ts": ts, "kind": kind, "label": text}
                if len(self.alerts) > 40:
                    self.alerts = self.alerts[-40:]
        except Exception:
            with self._lock:
                self.online = False

    def snapshot(self):
        with self._lock:
            return {
                "online": self.online, "running": self.running,
                "ok": self.ok, "fail": self.fail, "total": self.total,
                "last_task": self.last_task,
                "last_task_status": self.last_task_status,
                "last_poll_ok": self.last_poll_ok,
                "last_event": dict(self.last_event) if self.last_event else None,
                "alerts": list(self.alerts),
                "active_agents": dict(self.active_agents),
                "codex_seen": self.codex_seen,
                "codex_active": self.codex_active,
                "codex_mtime": self.codex_mtime,
                "codex_last": self.codex_last,
            }


# ─── Download detector ───────────────────────────────────────────

# Only real download locations are watched. Browser caches and %TEMP% are
# deliberately excluded: streaming video writes there continuously and would
# otherwise pin the Download view on screen forever.
DL_DIRS = [
    os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam",
                 "steamapps", "downloading"),
    os.path.join(os.environ.get("ProgramFiles", ""), "Steam",
                 "steamapps", "downloading"),
]

DL_HINTS = ("chrome", "msedge", "firefox", "brave", "opera", "vivaldi",
            "steam", "curl", "wget", "aria2", "qbittorrent", "transmission",
            "idman", "battle.net", "epicgames", "origin", "eaapp", "gog",
            "uplay", "ubisoft")

DL_MIN_GROWTH_MB = 0.30   # a watched file must grow at least this per poll (~1 s)
DL_MIN_NET_MB = 0.15      # and the link must carry at least this
DL_MIN_STREAK = 4         # qualifying polls in a row before showing (~4 s)
DL_MIN_TOTAL_MB = 3.0     # and this much transferred, so a page load can't trip it
DL_QUIET_STOP = 12        # polls without growth before hiding (~12 s)


class DownloadDetector:
    """Shows the Download view only for a genuine, sustained file download.

    A file must keep growing inside a real download folder *and* the network must
    be carrying traffic, repeatedly, for several seconds. Caches and %TEMP% are
    excluded so streaming video never triggers it.
    """

    def __init__(self):
        self.active = False
        self.name = ""
        self.speed = 0.0            # MB/s (recent)
        self.peak = 0.0
        self.total_mb = 0.0         # accumulated this download
        self.file = ""
        self.file_mb = 0.0
        self.started = 0.0
        self._last_rx = 0.0
        self._last_bytes = {}
        self._files = {}
        self._streak = 0
        self._quiet = 0
        self._name_t = 0.0
        self._name_cached = ""

    def _downloader_name(self):
        """Best-effort name of the downloading process (cosmetic only).

        Cached for 5 s: a process scan costs ~300 ms and this is called from the
        1 s download poll, which would otherwise hitch the render loop.
        """
        if not HAS_PSUTIL:
            return ""
        now = time.time()
        if now - self._name_t < 5.0:
            return self._name_cached
        best, best_rate = "", 0.0
        for p in psutil.process_iter(["pid", "name"]):
            try:
                nm = (p.info["name"] or "").lower()
                if not any(h in nm for h in DL_HINTS):
                    continue
                wr = p.io_counters().write_bytes
                prev = self._last_bytes.get(p.info["pid"])
                self._last_bytes[p.info["pid"]] = wr
                if prev is not None:
                    rate = (wr - prev) / (1024 ** 2)
                    if rate > best_rate:
                        best, best_rate = p.info["name"], rate
            except Exception:
                continue
        self._name_t = now
        self._name_cached = best
        return best

    def _fastest_growing(self):
        """(filename, size_mb, delta_mb) of the fastest-growing download file."""
        best = None
        for d in DL_DIRS:
            if not d or not os.path.isdir(d):
                continue
            try:
                for e in os.scandir(d):
                    if not e.is_file(follow_symlinks=False):
                        continue
                    try:
                        stt = e.stat()
                    except Exception:
                        continue
                    if time.time() - stt.st_mtime > 90:
                        continue
                    prev = self._files.get(e.path)
                    self._files[e.path] = stt.st_size
                    if prev is not None and stt.st_size > prev:
                        delta = (stt.st_size - prev) / (1024 ** 2)
                        if best is None or delta > best[2]:
                            best = (e.name, stt.st_size / (1024 ** 2), delta)
            except Exception:
                continue
        return best

    def poll(self, st):
        if not HAS_PSUTIL:
            return
        now = time.time()
        rx = st.get("net_recv", 0.0)
        rx_rate = (rx - self._last_rx) if self._last_rx else 0.0
        self._last_rx = rx

        # No traffic on the link means no download can be progressing, so skip
        # the directory scan entirely — it was the single biggest CPU consumer
        # in the whole loop (~10 % of a core at 1 Hz).
        if rx_rate < DL_MIN_NET_MB and not self.active:
            self._streak = 0
            self.total_mb = 0.0
            return

        found = self._fastest_growing()
        qualifies = (found is not None
                     and found[2] >= DL_MIN_GROWTH_MB
                     and rx_rate >= DL_MIN_NET_MB)

        if qualifies:
            self._quiet = 0
            self._streak += 1
            self.speed = rx_rate
            self.total_mb += found[2]
            self.file, self.file_mb = found[0], found[1]
            self.peak = max(self.peak, self.speed)
            if not self.active and self._streak >= DL_MIN_STREAK \
                    and self.total_mb >= DL_MIN_TOTAL_MB:
                self.active = True
                self.started = now
            if self.active:
                self.name = self._downloader_name() or self.name or found[0]
        else:
            self._streak = 0
            if self.active:
                self._quiet += 1
                if self._quiet > DL_QUIET_STOP:
                    self.active = False
                    self._quiet = 0
                    self.speed = 0.0
                    self.total_mb = 0.0
            else:
                self.total_mb = 0.0

    def snapshot(self):
        return {
            "active": self.active, "name": self.name,
            "speed": self.speed, "peak": self.peak,
            "total_mb": self.total_mb, "file": self.file,
            "file_mb": self.file_mb,
            "elapsed": (time.time() - self.started) if self.started else 0.0,
        }



# ─── VPS monitor (SSH, async) ──────────────────────────────────────

class VPSMonitor:
    """Polls a remote VPS via SSH for CPU, RAM, disk, uptime and top processes.

    Runs on its own thread with configurable poll interval.  If SSH fails
    ``max_retries`` times in a row it enters OFFLINE mode and retries less
    frequently.  When ``host`` is empty the monitor is disabled entirely and
    the VPS page is hidden.
    """

    def __init__(self):
        cfg = self._load_config()
        self.host = cfg.get("host", "")
        self.user = cfg.get("user", "root")
        self.key_path = cfg.get("key_path", "")
        self.poll_interval = cfg.get("poll_interval", 30)
        self.timeout = cfg.get("timeout", 5)
        self.max_retries = cfg.get("max_retries", 3)
        self.retry_interval = cfg.get("retry_interval", 60)
        self.enabled = bool(self.host)
        self._lock = threading.Lock()
        self.online = False
        self.cpu = 0.0
        self.ram = 0.0
        self.disk = 0.0
        self.uptime = ""
        self.top_procs = []       # [(name, cpu%), ...]
        self._fail_count = 0
        self._last_poll = 0.0

    @staticmethod
    def _load_config():
        try:
            with open(VPS_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _ssh_cmd(self):
        cmd = ["ssh", "-o", f"ConnectTimeout={self.timeout}",
               "-o", "StrictHostKeyChecking=no",
               "-o", "BatchMode=yes",
               "-o", f"ServerAliveInterval={self.timeout}"]
        if self.key_path:
            cmd += ["-i", self.key_path]
        cmd.append(f"{self.user}@{self.host}")
        return cmd

    def poll(self):
        """Collect VPS stats via SSH.  Called from a background thread."""
        if not self.enabled:
            return
        # If offline after max_retries, retry less frequently
        if self._fail_count >= self.max_retries:
            now = time.time()
            if now - self._last_poll < self.retry_interval:
                return
        cmd = self._ssh_cmd()
        # One round-trip: cat loadavg; echo ---; free -m; echo ---; df -h /; echo ---; uptime; echo ---; ps
        remote = (
            "cat /proc/loadavg; echo '---'; "
            "free -m | head -2; echo '---'; "
            "df -h / | tail -1; echo '---'; "
            "cat /proc/uptime; echo '---'; "
            "ps -eo %mem,%cpu,comm --sort=-%cpu | head -4"
        )
        try:
            r = subprocess.run(cmd + [remote], capture_output=True, timeout=self.timeout + 3,
                               creationflags=CREATE_NO_WINDOW)
            if r.returncode != 0:
                raise RuntimeError(f"ssh exit {r.returncode}")
            out = r.stdout.decode("utf-8", errors="replace")
            sections = out.split("---")
            now = time.time()

            # CPU from loadavg (1-min avg / cores approximation)
            cpu = 0.0
            if len(sections) > 0:
                parts = sections[0].strip().split()
                if len(parts) >= 1:
                    try:
                        load1 = float(parts[0])
                        # Approximate: load1 * 100 / cores; clamp
                        cores = os.cpu_count() or 1
                        cpu = min(100.0, load1 * 100.0 / max(cores, 1))
                    except ValueError:
                        pass

            # RAM from free -m
            ram = 0.0
            if len(sections) > 1:
                lines = sections[1].strip().splitlines()
                for line in lines:
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 3:
                            try:
                                used = int(parts[2])
                                total_str = parts[1]
                                total = int(total_str)
                                ram = (used / total * 100) if total else 0.0
                            except (ValueError, IndexError):
                                pass
                        break

            # Disk from df -h /
            disk = 0.0
            if len(sections) > 2:
                line = sections[2].strip()
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        disk = float(parts[4].rstrip("%"))
                    except ValueError:
                        pass

            # Uptime from /proc/uptime
            uptime_str = ""
            if len(sections) > 3:
                parts = sections[3].strip().split()
                if parts:
                    try:
                        up_s = float(parts[0])
                        d = int(up_s) // 86400
                        h = (int(up_s) % 86400) // 3600
                        m = (int(up_s) % 3600) // 60
                        if d > 0:
                            uptime_str = f"{d}d{h}h"
                        elif h > 0:
                            uptime_str = f"{h}h{m:02d}m"
                        else:
                            uptime_str = f"{m}m"
                    except ValueError:
                        uptime_str = sections[3].strip()[:12]

            # Top processes
            top_procs = []
            if len(sections) > 4:
                lines = sections[4].strip().splitlines()
                for line in lines[1:]:   # skip header
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            cpu_p = float(parts[0])
                            name = parts[2].split("/")[-1][:14]
                            top_procs.append((name, cpu_p))
                        except (ValueError, IndexError):
                            pass
                top_procs = top_procs[:3]

            with self._lock:
                self.online = True
                self.cpu = cpu
                self.ram = ram
                self.disk = disk
                self.uptime = uptime_str
                self.top_procs = top_procs
                self._fail_count = 0
                self._last_poll = now

        except Exception:
            with self._lock:
                self._fail_count += 1
                if self._fail_count >= self.max_retries:
                    self.online = False
                self._last_poll = time.time()

    def snapshot(self):
        with self._lock:
            return {
                "enabled": self.enabled,
                "online": self.online,
                "cpu": self.cpu,
                "ram": self.ram,
                "disk": self.disk,
                "uptime": self.uptime,
                "top_procs": list(self.top_procs),
                "host": self.host,
                "fail_count": self._fail_count,
            }

# ─── system stats ────────────────────────────────────────────────

_net = {"sent": 0.0, "recv": 0.0, "t": 0.0, "up": 0.0, "dn": 0.0}
NET_HIST = []          # sparkline history (KB/s)

# psutil.process_iter() costs ~300 ms on this machine, so the two parts of the
# stats are cached separately: cheap counters refresh every second, the process
# scan only every few seconds. Without this the loop burned ~1.7 s of CPU per
# second of wall clock.
STATS_TTL = 1.0
TOP_TTL = 3.0
_base_cache = {"t": 0.0, "data": {}}
_top_cache = {"t": 0.0, "data": [], "busy": False}

# psutil reports these as top CPU consumers but they are just Windows bookkeeping
# (System Idle Process is literally idle time).
SKIP_PROCS = {"", "system idle process", "system", "idle", "memory compression"}


def _collect_base(st):
    st["cpu"] = psutil.cpu_percent(interval=None)
    f = psutil.cpu_freq()
    st["cpu_freq"] = f.current if f else 0
    m = psutil.virtual_memory()
    st["mem"] = m.percent
    st["mem_used"] = m.used / (1024 ** 3)
    st["mem_total"] = m.total / (1024 ** 3)
    d = psutil.disk_usage("C:\\")
    st["disk"] = d.percent
    st["disk_used"] = d.used / (1024 ** 3)
    st["disk_total"] = d.total / (1024 ** 3)
    n = psutil.net_io_counters()
    now = time.time()
    sent = n.bytes_sent / (1024 ** 2)
    recv = n.bytes_recv / (1024 ** 2)
    dt = now - _net["t"]
    if dt > 0 and _net["t"] > 0:
        _net["up"] = (sent - _net["sent"]) / dt
        _net["dn"] = (recv - _net["recv"]) / dt
    _net.update(sent=sent, recv=recv, t=now)
    st["net_up"], st["net_dn"] = _net["up"], _net["dn"]
    st["net_sent"], st["net_recv"] = sent, recv
    NET_HIST.append(_net["dn"] * 1024)
    if len(NET_HIST) > 60:
        del NET_HIST[:-60]
    try:
        temps = psutil.sensors_temperatures()
        tl = []
        if temps:
            for name, entries in temps.items():
                for e in entries:
                    if e.current is not None:
                        tl.append((e.label or name, e.current))
        st["temps"] = tl
    except Exception:
        st["temps"] = []
    st["procs"] = len(psutil.pids())
    st["uptime"] = time.time() - psutil.boot_time()
    return st


def _collect_top():
    procs = []
    for p in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
        try:
            i = p.info
            nm = (i.get("name") or "").strip()
            if nm.lower() in SKIP_PROCS or i["cpu_percent"] is None:
                continue
            procs.append(i)
        except Exception:
            continue
    procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
    return procs[:3]


def _refresh_top_async():
    """Scan processes off the render thread: it costs ~350 ms on this machine."""
    if _top_cache["busy"]:
        return
    _top_cache["busy"] = True

    def work():
        try:
            _top_cache["data"] = _collect_top()
            _top_cache["t"] = time.time()
        except Exception:
            pass
        finally:
            _top_cache["busy"] = False

    threading.Thread(target=work, daemon=True).start()


def get_system_stats():
    if not HAS_PSUTIL:
        return {}
    now = time.time()
    st = _base_cache["data"]
    try:
        if not st or now - _base_cache["t"] >= STATS_TTL:
            st = _collect_base(st)
            _base_cache.update(t=now, data=st)
        if now - _top_cache["t"] >= TOP_TTL:
            _refresh_top_async()
        st["top"] = _top_cache["data"]
    except Exception:
        pass
    return st


# ─── graphics toolkit ────────────────────────────────────────────

class Gfx:
    """Small drawing helpers on a 160x43 1-bit canvas."""

    def __init__(self):
        self.font = None
        self.font_small = None
        self.dots = None          # (index, total) page indicator, set per frame
        if HAS_PIL:
            # Consolas Bold survives 1-bit thresholding far better than regular:
            # at threshold 128 regular Consolas loses 'o','N','P' right-side strokes.
            # 11 px for titles, 10 px for body — 9 px degrades once binarised
            # (CPU read as CPV, RAM as AAM).
            for cand in ("consolab.ttf", "consola.ttf", "lucon.ttf"):
                p = os.path.join(r"C:\Windows\Fonts", cand)
                if os.path.exists(p):
                    try:
                        self.font = ImageFont.truetype(p, 11)
                        self.font_small = ImageFont.truetype(p, 10)
                        break
                    except Exception:
                        pass
            if self.font is None:
                self.font = ImageFont.load_default()
            if self.font_small is None:
                self.font_small = self.font

    def page_dots(self, d, dots=None):
        """Seven page dots pinned to the top-right: the current page indicator.

        Pinned to a fixed position so every page carries it identically; the
        current page is the filled one.
        """
        dots = dots if dots is not None else self.dots
        if not dots:
            return
        idx, total = dots
        bx = W - 4 - ((total - 1) * 3 + 3)
        for i in range(total):
            cx = bx + i * 3
            if i == idx:
                d.rectangle([cx, 4, cx + 2, 6], fill=255)
            else:
                d.point((cx + 1, 5), fill=255)

    def frame(self, d, title, right="", dots=None):
        """Shared page chrome: 11 px title, right context, 1 px rule, page balls.

        Every page uses this so the panel reads as one consistent instrument
        instead of seven unrelated screens.
        """
        dots = dots if dots is not None else self.dots
        total = dots[1] if dots else 0
        t = ascii_text(title)
        d.text((4, -1), t, font=self.font, fill=255)
        tw = d.textlength(t, font=self.font)
        d.line([(0, 12), (W - 1, 12)], fill=255)
        self.page_dots(d, dots)
        if right:
            r = ascii_text(right)
            rw = d.textlength(r, font=self.font_small)
            rx = (W - 10 - ((total - 1) * 3 + 3) - rw) if total else (W - 4 - rw)
            if rx > tw + 6:
                d.text((rx, 0), r, font=self.font_small, fill=255)

    @staticmethod
    def canvas():
        img = Image.new("L", (W, H), 0)
        return img, ImageDraw.Draw(img)

    def text(self, d, xy, s, small=False):
        d.text(xy, ascii_text(s), font=(self.font_small if small else self.font), fill=255)

    @staticmethod
    def hline(d, y, x0=0, x1=W - 1):
        d.line([(x0, y), (x1, y)], fill=255)

    @staticmethod
    def hbar(d, x, y, w, h, pct, fill=255, outline=True):
        pct = max(0.0, min(1.0, pct))
        if outline:
            d.rectangle([x, y, x + w - 1, y + h - 1], outline=fill)
            inner_w = max(0, int((w - 2) * pct))
            if inner_w > 0:
                d.rectangle([x + 1, y + 1, x + inner_w, y + h - 2], fill=fill)
        else:
            inner_w = max(0, int(w * pct))
            if inner_w:
                d.rectangle([x, y, x + inner_w - 1, y + h - 1], fill=fill)

    @staticmethod
    def stripes(d, x, y, w, h, phase):
        """Indeterminate bar: moving blocks."""
        blk = 8
        off = int(phase) % (blk * 2)
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=255)
        xx = x + 1 - off
        while xx < x + w - 1:
            x0 = max(xx, x + 1)
            x1 = min(xx + blk - 1, x + w - 2)
            if x1 >= x0:
                d.rectangle([x0, y + 1, x1, y + h - 2], fill=255)
            xx += blk * 2

    @staticmethod
    def sparkline(d, x, y, w, h, values):
        if not values:
            return
        vals = values[-w:]
        mx = max(vals) or 1.0
        n = len(vals)
        pts = []
        for i, v in enumerate(vals):
            px = x + int(i * (w - 1) / max(1, n - 1))
            py = y + h - 1 - int((v / mx) * (h - 1))
            pts.append((px, py))
        if len(pts) > 1:
            d.line(pts, fill=255)


# ─── agent face ──────────────────────────────────────────────────

def self_alert(st, oc):
    s = oc.snapshot()
    ev = s.get("last_event")
    if ev and ev["kind"] == "fail" and (time.time() - ev["ts"] < 8):
        return True
    return (st.get("cpu", 0) > 95) or (st.get("mem", 0) > 95)


# ─── mascots ───────────────────────────────────────────────────

MASCOT_COLOR = {
    "pc": (0, 70, 95),        # blue
    "openclaw": (0, 88, 92),   # cyan
    "codex": (15, 92, 48),     # green
}
ACTIVE_COLOR = (95, 80, 0)        # highlight while a source is busy
FLASH_COLOR = (0, 60, 100)        # download / transfer accent
MASCOT_NAME = {"pc": "PC", "openclaw": "CLAW", "codex": "CODEX"}


def build_sources(st, oc, dl):
    """The three things the panel watches: the PC, OpenClaw and Codex."""
    s = oc.snapshot()
    agents = s.get("active_agents") or {}
    now = time.time()
    codex_age = (now - s["codex_mtime"]) if s.get("codex_mtime") else None
    return [
        {
            "key": "pc", "label": "PC", "online": True,
            "busy": st.get("cpu", 0) > 55,
            "detail": f"cpu {st.get('cpu', 0):.0f}% ram {st.get('mem', 0):.0f}%",
        },
        {
            "key": "openclaw", "label": "CLAW",
            "online": bool(s.get("online")),
            "busy": bool(agents) or s.get("running", 0) > 0,
            "detail": f"run {sum(agents.values()) or s.get('running', 0)} "
                      f"ok {s.get('ok', 0)}",
        },
        {
            "key": "codex", "label": "CODEX",
            "online": bool(s.get("codex_seen")),
            "busy": bool(s.get("codex_active")),
            "detail": (f"{age_str(s['codex_mtime'])} ago" if codex_age is not None
                       else "not found"),
        },
    ]


def pick_active(sources):
    """The source to feature: whichever agent is busy, else OpenClaw, else the PC."""
    for s in sources:
        if s["key"] != "pc" and s["busy"]:
            return s
    for s in sources:
        if s["key"] == "openclaw" and s["online"]:
            return s
    return sources[0]


def mood_for(st, oc, dl, src):
    """Expression for the featured mascot."""
    if self_alert(st, oc):
        return "alarm"
    s = oc.snapshot()
    ev = s.get("last_event")
    if ev and (time.time() - ev["ts"] < 8):
        return "happy" if ev["kind"] == "ok" else "alarm"
    if dl.active:
        return "focus"
    if src and src.get("busy"):
        return "watch"
    cpu, mem = st.get("cpu", 0), st.get("mem", 0)
    if cpu > 90 or mem > 90 or st.get("disk", 0) > 95:
        return "worried"
    return "idle"


def load_index(st, oc, dl):
    """A single 'load index' derived from real machine and agent activity.

    Purely presentational: it folds CPU/RAM/disk/network plus running agents into
    one number, so a busy machine visibly reads higher.
    """
    s = oc.snapshot()
    pl = 1000.0
    pl += (st.get("cpu", 0) or 0) * 42
    pl += (st.get("mem", 0) or 0) * 26
    pl += (st.get("disk", 0) or 0) * 6
    pl += min((st.get("net_dn", 0) or 0) * 3, 2000)
    pl += sum((s.get("active_agents") or {}).values()) * 4500
    if dl.active:
        pl += min((dl.snapshot().get("speed") or 0) * 2500, 6000)
    return int(pl)


def is_busy(st, oc, dl, src):
    """True when the machine or the agents are busy enough to warrant a highlight."""
    s = oc.snapshot()
    return bool(
        (src and src.get("busy"))
        or dl.active
        or (st.get("cpu", 0) or 0) > 70
        or sum((s.get("active_agents") or {}).values()) > 0
    )


class MascotRenderer:
    """Three hand-drawn 1-bit mascots with blinking, bobbing and idle glances."""

    def __init__(self, gfx):
        self.gfx = gfx
        self._blink_next = time.time() + 3.0
        self._blink_until = 0.0
        self._look = 0
        self._look_next = time.time() + 4.0

    def _anim(self):
        now = time.time()
        blinking = now < self._blink_until
        if now > self._blink_next:
            self._blink_until = now + 0.12
            self._blink_next = now + 2.2 + (hash(int(now)) % 30) / 10.0
            blinking = True
        if now > self._look_next:
            self._look = (-2, 0, 2)[hash(int(now)) % 3]
            self._look_next = now + 2.5 + (hash(int(now * 7)) % 25) / 10.0
        bob = int(round(1.4 * math.sin(now * 2.3)))
        return blinking, bob

    # ---- big versions
    def _activity_flare(self, d, cx, cy):
        """Energy flares bursting sideways from the mascot while it is busy.

        Sideways rather than upward: the head sits near the top edge of a 43 px
        panel, so vertical spikes would just be clipped.
        """
        for dx, dy in ((-18, -6), (-18, 3), (18, -6), (18, 3),
                       (-12, -13), (12, -13)):
            d.line([(cx + dx, cy + dy),
                    (cx + int(dx * 1.55), cy + int(dy * 1.35 + (2 if dy > 0 else -2)))],
                   fill=255)

    def draw(self, d, key, cx, cy, mood, busy=False):
        blinking, bob = self._anim()
        cy += bob
        if busy:
            self._activity_flare(d, cx, cy)
        if key == "openclaw":
            self._claw(d, cx, cy, mood, blinking)
        elif key == "codex":
            self._codex(d, cx, cy, mood, blinking)
        else:
            self._pc(d, cx, cy, mood, blinking)

    def _eyes(self, d, cx, cy, gap, r, blinking):
        if blinking:
            d.line([(cx - gap - r, cy), (cx - gap + r, cy)], fill=255)
            d.line([(cx + gap - r, cy), (cx + gap + r, cy)], fill=255)
            return
        for ex in (cx - gap, cx + gap):
            d.ellipse([ex - r, cy - r, ex + r, cy + r], outline=255)
            lx = self._look
            d.ellipse([ex + lx - 1, cy - 1, ex + lx + 1, cy + 1], fill=255)

    def _mouth(self, d, cx, cy, mood):
        if mood == "happy":
            d.arc([cx - 6, cy - 5, cx + 6, cy + 4], 20, 160, fill=255)
        elif mood == "alarm":
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline=255)
        elif mood == "worried":
            d.line([(cx - 5, cy + 1), (cx + 5, cy + 1)], fill=255)
        else:
            d.line([(cx - 4, cy), (cx + 4, cy)], fill=255)

    def _claw(self, d, cx, cy, mood, blinking):
        """OpenClaw: a little crab."""
        d.rounded_rectangle([cx - 15, cy - 10, cx + 15, cy + 11],
                            radius=8, outline=255)
        # claws (open when attentive)
        spread = 3 if mood in ("watch", "happy", "focus") else 0
        d.arc([cx - 25 - spread, cy - 12, cx - 13 + spread, cy + 2], 90, 280, fill=255)
        d.arc([cx + 13 - spread, cy - 12, cx + 25 + spread, cy + 2], 260, 90, fill=255)
        # legs
        for dy in (-5, 0, 5):
            d.line([(cx - 15, cy + dy), (cx - 21, cy + dy + 3)], fill=255)
            d.line([(cx + 15, cy + dy), (cx + 21, cy + dy + 3)], fill=255)
        # eyes on stalks above the shell
        ey = cy - 16
        d.line([(cx - 7, cy - 10), (cx - 7, ey + 3)], fill=255)
        d.line([(cx + 7, cy - 10), (cx + 7, ey + 3)], fill=255)
        self._eyes(d, cx, ey, 7, 3, blinking)
        self._mouth(d, cx, cy + 5, mood)

    def _codex(self, d, cx, cy, mood, blinking):
        """Codex: a robot with a scanning visor."""
        d.rounded_rectangle([cx - 15, cy - 12, cx + 15, cy + 13],
                            radius=4, outline=255)
        d.line([(cx, cy - 12), (cx, cy - 17)], fill=255)
        if int(time.time() * 2) % 2 == 0:
            d.ellipse([cx - 2, cy - 20, cx + 2, cy - 16], fill=255)
        else:
            d.ellipse([cx - 2, cy - 20, cx + 2, cy - 16], outline=255)
        vx0, vx1, vy0, vy1 = cx - 11, cx + 11, cy - 7, cy + 1
        d.rectangle([vx0, vy0, vx1, vy1], outline=255)
        if blinking:
            d.line([(vx0 + 1, (vy0 + vy1) // 2), (vx1 - 1, (vy0 + vy1) // 2)], fill=255)
        else:
            span = (vx1 - vx0) - 8
            px = vx0 + 1 + int(span * (0.5 + 0.5 * math.sin(time.time() * 1.7)))
            d.rectangle([px, vy0 + 1, px + 5, vy1 - 1], fill=255)
        for row in range(2):
            for col in range(4):
                x = cx - 9 + col * 5
                y = cy + 5 + row * 4
                filled = (mood == "happy") or ((row * 4 + col) % 3 != 2)
                if filled:
                    d.rectangle([x, y, x + 2, y + 2], fill=255)
                else:
                    d.rectangle([x, y, x + 2, y + 2], outline=255)

    def _pc(self, d, cx, cy, mood, blinking):
        """Your PC: a monitor with a face."""
        d.rounded_rectangle([cx - 16, cy - 13, cx + 16, cy + 7],
                            radius=3, outline=255)
        d.line([(cx, cy + 7), (cx, cy + 12)], fill=255)
        d.line([(cx - 7, cy + 12), (cx + 7, cy + 12)], fill=255)
        self._eyes(d, cx, cy - 5, 8, 3, blinking)
        self._mouth(d, cx, cy + 2, mood)

    # ---- mini versions for the sources strip
    def draw_mini(self, d, key, cx, cy, busy):
        if key == "openclaw":
            d.ellipse([cx - 8, cy - 5, cx + 8, cy + 6], outline=255)
            d.arc([cx - 14, cy - 6, cx - 7, cy + 2], 100, 270, fill=255)
            d.arc([cx + 7, cy - 6, cx + 14, cy + 2], 270, 80, fill=255)
            d.line([(cx - 4, cy - 5), (cx - 4, cy - 8)], fill=255)
            d.line([(cx + 4, cy - 5), (cx + 4, cy - 8)], fill=255)
            d.ellipse([cx - 5, cy - 10, cx - 3, cy - 8], fill=255)
            d.ellipse([cx + 3, cy - 10, cx + 5, cy - 8], fill=255)
        elif key == "codex":
            d.rounded_rectangle([cx - 8, cy - 6, cx + 8, cy + 6],
                                radius=2, outline=255)
            d.line([(cx, cy - 6), (cx, cy - 9)], fill=255)
            if busy:
                d.rectangle([cx - 5, cy - 2, cx + 5, cy + 1], fill=255)
            else:
                d.rectangle([cx - 5, cy - 2, cx + 5, cy + 1], outline=255)
        else:
            d.rounded_rectangle([cx - 8, cy - 7, cx + 8, cy + 4],
                                radius=2, outline=255)
            d.line([(cx, cy + 4), (cx, cy + 7)], fill=255)
            d.line([(cx - 4, cy + 7), (cx + 4, cy + 7)], fill=255)
            d.ellipse([cx - 4, cy - 3, cx - 2, cy - 1], fill=255)
            d.ellipse([cx + 2, cy - 3, cx + 4, cy - 1], fill=255)


# ─── pages (bitmap) ──────────────────────────────────────────────

class Page:
    name = "Page"

    def render(self, gfx, d, st, oc, dl, ctx):
        pass


def _alert_icon(d, x, y, kind):
    """Small severity glyph: bang for failures, tick for successes, dot for info."""
    if kind == "fail":
        # narrow bar + separated dot, or the two merge into a solid block
        d.rectangle([x + 2, y, x + 3, y + 5], fill=255)
        d.rectangle([x + 2, y + 7, x + 3, y + 8], fill=255)
    elif kind == "ok":
        d.line([(x, y + 5), (x + 3, y + 8)], fill=255)
        d.line([(x + 3, y + 8), (x + 7, y + 1)], fill=255)
    else:
        d.rectangle([x + 2, y + 3, x + 4, y + 5], fill=255)


class MascotPage(Page):
    name = "Mascot"

    def render(self, gfx, d, st, oc, dl, ctx):
        mascot = ctx["mascot"]
        src = ctx["active_source"]
        mood = ctx["mood"]
        mascot.draw(d, src["key"], 29, 18, mood, busy=ctx.get("busy", False))
        d.line([(6, 38), (52, 38)], fill=255)     # ground line
        d.line([(58, 1), (58, 41)], fill=255)     # column separator
        gfx.page_dots(d)
        gfx.text(d, (63, 0), src["label"])
        gfx.text(d, (63, 15), clip(src["detail"], 15), small=True)
        state = "BUSY" if src["busy"] else ("OK" if src["online"] else "OFFLINE")
        gfx.text(d, (63, 25), state, small=True)
        gfx.text(d, (63, 34), f"LOAD {ctx.get('load', 0):,}", small=True)


class SourcesPage(Page):
    name = "Sources"

    def render(self, gfx, d, st, oc, dl, ctx):
        srcs = ctx["sources"]
        gfx.frame(d, "SOURCES", f"{sum(1 for s in srcs if s['online'])}/3 up")
        mascot = ctx["mascot"]
        for i, s in enumerate(srcs):
            cx = 27 + i * 53
            mascot.draw_mini(d, s["key"], cx, 23, s["busy"])
            w = d.textlength(s["label"], font=gfx.font_small)
            gfx.text(d, (int(cx - w / 2), 31), s["label"], small=True)
            if s["busy"]:
                d.rectangle([cx - 2, 40, cx + 2, 41], fill=255)
            elif s["online"]:
                d.rectangle([cx - 2, 40, cx + 2, 41], outline=255)
            else:
                d.line([(cx - 2, 40), (cx + 2, 41)], fill=255)
                d.line([(cx - 2, 41), (cx + 2, 40)], fill=255)


class SystemPage(Page):
    name = "System"

    def render(self, gfx, d, st, oc, dl, ctx):
        gfx.frame(d, "SYSTEM", fmt_uptime(st.get("uptime", 0)))
        y = 13
        for label, pct in (("CPU", st.get("cpu", 0)),
                           ("RAM", st.get("mem", 0)),
                           ("DSK", st.get("disk", 0))):
            gfx.text(d, (3, y), f"{label} {pct:5.1f}%", small=True)
            gfx.hbar(d, 62, y + 1, 95, 8, pct / 100.0)
            y += 10


class NetworkPage(Page):
    name = "Network"

    def render(self, gfx, d, st, oc, dl, ctx):
        gfx.frame(d, "NETWORK", f"tot {fmt_bytes(st.get('net_recv', 0))}")
        gfx.text(d, (3, 13), f"DN {fmt_speed(st.get('net_dn', 0))}", small=True)
        gfx.text(d, (3, 23), f"UP {fmt_speed(st.get('net_up', 0))}", small=True)
        gfx.text(d, (3, 33), f"sent {fmt_bytes(st.get('net_sent', 0))}", small=True)
        gfx.sparkline(d, 86, 14, 71, 28, NET_HIST)


class ProcsPage(Page):
    name = "Procs"

    def render(self, gfx, d, st, oc, dl, ctx):
        gfx.frame(d, "PROCESSES", str(st.get("procs", "?")))
        procs = (st.get("top") or [])
        if not procs:
            gfx.text(d, (3, 20), "sampling...", small=True)
            return
        y = 13
        for p in procs[:3]:
            n = clip(p.get("name") or "?", 14)
            c = p.get("cpu_percent", 0) or 0
            gfx.text(d, (3, y), n, small=True)
            gfx.text(d, (90, y), f"{c:3.0f}%", small=True)
            gfx.hbar(d, 116, y + 1, 41, 8, min(1.0, c / 100.0), outline=True)
            y += 10


class OpenClawPage(Page):
    name = "OpenClaw"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        gfx.frame(d, "OPENCLAW", "link up" if s["online"] else "OFFLINE")
        if s["online"]:
            gfx.text(d, (3, 13), f"run {s['running']}  ok {s['ok']}  fail {s['fail']}", small=True)
            gfx.text(d, (3, 23), clip(s["last_task"], 25), small=True)
            poll = age_str(s["last_poll_ok"]) if s["last_poll_ok"] else "--"
            gfx.text(d, (3, 33), f"{clip(s['last_task_status'], 12)} poll {poll}", small=True)
        else:
            gfx.text(d, (3, 15), "bridge offline", small=True)
            gfx.text(d, (3, 25), "wsl lcd-probe", small=True)
            gfx.text(d, (3, 35), "not responding", small=True)


class AlertsPage(Page):
    name = "Alerts"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        items = []          # (ts, kind, text)
        now = time.time()
        if st.get("cpu", 0) > 90:
            items.append((now, "fail", f"CPU HIGH {st['cpu']:.0f}%"))
        if st.get("mem", 0) > 90:
            items.append((now, "fail", f"RAM HIGH {st['mem']:.0f}%"))
        if st.get("disk", 0) > 95:
            items.append((now, "fail", f"DISK {st['disk']:.0f}%"))
        for ts, kind, text in s["alerts"][-6:]:
            items.append((ts, kind, text))

        if not items:
            gfx.frame(d, "ALERTS", "none")
            gfx.text(d, (3, 15), "all systems ok", small=True)
            gfx.text(d, (3, 25), f"agents {s['ok']} ok {s['fail']} fail", small=True)
            return
        gfx.frame(d, f"ALERTS ({len(items)})", RGB_STATE["effect"][:11])
        y = 13
        for ts, kind, text in items[-3:]:
            _alert_icon(d, 2, y + 1, kind)
            gfx.text(d, (12, y), f"{clip(text, 23)} {age_str(ts)}", small=True)
            y += 10


class StatusPage(Page):
    """B3 scouter: power level + CPU temp + gateway + active agents.

    Shows for 5 seconds then returns to the current page (B3 timeout).
    """

    name = "Status"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        gfx.frame(d, "SCOUTER", f"PL {ctx.get('load', 0):,}")
        y = 13
        # CPU / RAM / DSK bars
        for label, pct in (("CPU", st.get("cpu", 0)),
                           ("RAM", st.get("mem", 0)),
                           ("DSK", st.get("disk", 0))):
            gfx.text(d, (3, y), f"{label} {pct:5.1f}%", small=True)
            gfx.hbar(d, 62, y + 1, 70, 8, pct / 100.0)
            y += 10

        # CPU temperature if available (via psutil)
        temps = st.get("temps", [])
        temp_str = ""
        if temps:
            # Use first CPU/package temperature
            for name, val in temps:
                low = name.lower()
                if "core" in low or "cpu" in low or "package" in low or "tctl" in low:
                    temp_str = f" {val:.0f}" + chr(176) + "C"
                    break
            if not temp_str:
                temp_str = f" {temps[0][1]:.0f}" + chr(176) + "C"
        gfx.text(d, (135, 13), clip(temp_str, 8), small=True)

        # Gateway status (openclaw online/offline)
        gw_status = "GW UP" if s.get("online") else "GW DOWN"
        gw_color_hint = "ok" if s.get("online") else "fail"
        # Small indicator: filled dot = up, empty dot = down
        if s.get("online"):
            d.ellipse([148, y + 2, 154, y + 8], fill=255)   # filled green dot
        else:
            d.ellipse([148, y + 2, 154, y + 8], outline=255)  # hollow red dot

        agents_count = sum((s.get("active_agents") or {}).values())
        agent_str = f"AG{agents_count}" if agents_count else "AG0"
        gw_str = f"{gw_status} {agent_str}"
        gfx.text(d, (3, y), clip(gw_str, 20), small=True)
        y += 10

        # Codex line
        if s.get("codex_active"):
            codex = "CODEX active"
        elif s.get("codex_mtime"):
            codex = f"CODEX {age_str(s['codex_mtime'])} ago"
        else:
            codex = "CODEX n/a"
        gfx.text(d, (3, y), clip(codex, 25), small=True)


class DownloadPage(Page):
    name = "Download"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = dl.snapshot()
        gfx.frame(d, "DOWNLOADING", fmt_speed(s["speed"]))
        gfx.stripes(d, 2, 15, 156, 12, time.time() * 26)
        if int(time.time()) % 2 == 0:
            gfx.text(d, (3, 30), f"{clip(s['name'] or 'download', 11)} {fmt_bytes(s['total_mb'])}", small=True)
        else:
            gfx.text(d, (3, 30), clip(s["file"] or f"{int(s['elapsed'])}s elapsed", 25), small=True)


class VPSPage(Page):
    name = "VPS"

    def render(self, gfx, d, st, oc, dl, ctx):
        vps = ctx.get("vps_snapshot", {})
        online = vps.get("online", False)
        host = vps.get("host", "?")
        if not online:
            if vps.get("fail_count", 0) >= 3:
                label = "VPS OFFLINE"
            else:
                label = "VPS CONNECT..."
            gfx.frame(d, "VPS", label)
            gfx.text(d, (3, 15), clip(host, 20), small=True)
            # Red indicator dot
            d.ellipse([148, 3, 155, 10], fill=255)
            d.ellipse([149, 4, 154, 9], fill=0)    # hollow = red
            d.ellipse([150, 5, 153, 8], fill=255)   # dot inside = red alert
            retries = vps.get("fail_count", 0)
            gfx.text(d, (3, 25), f"retries {retries}", small=True)
            gfx.text(d, (3, 35), "SSH failed", small=True)
            return

        # Green connection indicator
        d.rectangle([148, 4, 155, 9], fill=255)

        gfx.frame(d, "VPS", vps.get("uptime", "?"))
        y = 13
        for label, pct in (("CPU", vps.get("cpu", 0)),
                           ("RAM", vps.get("ram", 0)),
                           ("DSK", vps.get("disk", 0))):
            gfx.text(d, (3, y), f"{label} {pct:5.1f}%", small=True)
            gfx.hbar(d, 62, y + 1, 95, 8, pct / 100.0)
            y += 10

        procs = vps.get("top_procs", [])
        if procs:
            for name, cpu_p in procs[:3]:
                n = clip(name, 14)
                gfx.text(d, (3, y), n, small=True)
                gfx.text(d, (90, y), f"{cpu_p:3.0f}%", small=True)
                y += 8



# ─── app ─────────────────────────────────────────────────────────

class LCDGlance:
    def __init__(self):
        self.lcd = LCDController()
        self.led = LEDController()
        self.oc = OpenClawMonitor()
        self.dl = DownloadDetector()
        self.vps = VPSMonitor()
        self.gfx = Gfx()
        self.mascot = MascotRenderer(self.gfx)
        self.rgb = None
        self.pages = [MascotPage(), SourcesPage(), SystemPage(), NetworkPage(),
                      ProcsPage(), OpenClawPage(), AlertsPage()]
        if self.vps.enabled:
            self.pages.append(VPSPage())
        self.mascot_page = self.pages[0]
        self.status_page = StatusPage()
        self.dl_page = DownloadPage()
        self.page = 0
        self.prev_buttons = 0
        self.running = False
        self._btn_ts = 0.0
        self.status_until = 0.0
        self.flash_until = 0.0
        self._last_bitmap = None
        self._last_submit = 0.0
        self._last_render = 0.0
        self._override = None      # {"page": obj|None, "until": ts, "kind": str}
        self._dl_was_active = False
        self._ev_seen = 0.0

    # ---- lifecycle
    def start(self):
        print("LCDGlance v7.1 — G510 mascots + RGB + agent alerts", flush=True)
        print("=" * 60, flush=True)

        if not HAS_PIL:
            print("[!] Pillow missing — graphics unavailable", flush=True)
            return
        if not HAS_PSUTIL:
            print("[!] psutil missing — stats unavailable", flush=True)

        kill_lcd_applets()
        self.lcd.connect()
        self.led.connect()
        self.rgb = RGBEngine(self.led, self.oc, self.dl, self.vps)

        if not self.lcd.connected and not self.led.connected:
            print("[!] No Logitech devices. Is LGS running?", flush=True)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return

        self.running = True
        print(f"Pages: {[p.name for p in self.pages]}", flush=True)
        print("B1/B2 pages  B3 scouter  B4 alert", flush=True)
        if self.vps.enabled:
            print(f"VPS: {self.vps.user}@{self.vps.host} (poll {self.vps.poll_interval}s)", flush=True)
        else:
            print("VPS: disabled (no host in vps_config.json)", flush=True)

        self._splash()
        self.rgb.sweep()

        threading.Thread(target=self._oc_loop, daemon=True).start()
        threading.Thread(target=self._dl_loop, daemon=True).start()
        if self.vps.enabled:
            threading.Thread(target=self._vps_loop, daemon=True).start()

        try:
            self._loop()
        except KeyboardInterrupt:
            print("\nStopping...", flush=True)
        finally:
            self.stop()

    def _splash(self):
        img, d = self.gfx.canvas()
        self.mascot.draw(d, "openclaw", 28, 21, "happy")
        self.gfx.text(d, (56, 6), "LCDGlance v7")
        self.gfx.text(d, (56, 20), "PC / CLAW / CODEX", small=True)
        self.gfx.text(d, (56, 31), "agent alerts", small=True)
        if self.lcd.connected:
            self.lcd.set_bitmap(img)
            self.lcd.update()
            time.sleep(2.0)

    def _oc_loop(self):
        try:
            self.oc.poll()
        except Exception:
            pass
        while self.running:
            try:
                time.sleep(OC_POLL_INTERVAL)
                if not self.running:
                    break
                try:
                    self.oc.poll()
                except Exception:
                    pass
            except Exception:
                # a bad poll must not kill the thread
                traceback.print_exc()
                time.sleep(1.0)

    def _dl_loop(self):
        while self.running:
            try:
                self.dl.poll(get_system_stats())
            except Exception:
                pass
            time.sleep(DL_POLL_INTERVAL)

    def _vps_loop(self):
        try:
            self.vps.poll()
        except Exception:
            pass
        while self.running:
            try:
                time.sleep(self.vps.poll_interval)
                if not self.running:
                    break
                try:
                    self.vps.poll()
                except Exception:
                    pass
            except Exception:
                traceback.print_exc()
                time.sleep(1.0)

    # ---- auto-focus (the "smart" part)
    def _update_override(self, now):
        s = self.oc.snapshot()
        ev = s.get("last_event")

        # an agent finished -> jump to its mascot reacting for a few seconds
        if ev and ev["ts"] != self._ev_seen:
            self._ev_seen = ev["ts"]
            self._override = {"page": self.mascot_page, "until": now + 8.0,
                              "kind": "event"}

        # download running -> show download view until it ends
        if self.dl.active:
            self._dl_was_active = True
            self._override = {"page": self.dl_page, "until": now + 1.5,
                              "kind": "download"}
        elif self._dl_was_active:
            self._dl_was_active = False
            if self._override and self._override["kind"] == "download":
                self._override = {"page": self.mascot_page, "until": now + 4.0,
                                  "kind": "event"}

        if self._override and now > self._override["until"]:
            self._override = None

    # ---- main loop
    def _loop(self):
        reconnect_at = kill_at = 0.0
        while self.running:
            try:
                now = time.time()
                if now - reconnect_at > LCD_CHECK_INTERVAL:
                    self.lcd.ensure_connected()
                    reconnect_at = now
                # LGS only spawns its LCD applets on demand, so sweeping rarely is
                # enough — and each sweep spawns six taskkill processes.
                if now - kill_at > 300:
                    kill_lcd_applets()
                    kill_at = now

                st = get_system_stats()
                self._check_buttons()
                self._update_override(now)

                sources = build_sources(st, self.oc, self.dl)
                active = pick_active(sources)
                # computed every tick: the RGB engine needs it even on frames the
                # render gate skips, and it is cheap (both snapshots are cached)
                load = load_index(st, self.oc, self.dl)
                busy = is_busy(st, self.oc, self.dl, active)
                if self.rgb:
                    self.rgb.active_source_key = active["key"]
                    self.rgb.busy = busy

                if self.lcd.connected:
                    if now < self.flash_until:
                        page = self.pages[self.page]
                    elif now < self.status_until:
                        page = self.status_page
                    elif self._override and self._override["page"]:
                        page = self._override["page"]
                    else:
                        page = self.pages[self.page]
                    animated = (page is self.mascot_page or page is self.dl_page
                                or now < self.flash_until or now < self.status_until)
                    interval = ANIM_INTERVAL if animated else STATIC_INTERVAL
                    self.gfx.dots = (self.page, len(self.pages))
                    if now - self._last_render >= interval:
                        self._last_render = now
                        ctx = {"mascot": self.mascot, "sources": sources,
                               "active_source": active,
                               "mood": mood_for(st, self.oc, self.dl, active),
                               "load": load, "busy": busy,
                               "vps_snapshot": self.vps.snapshot()}
                        img, d = self.gfx.canvas()
                        page.render(self.gfx, d, st, self.oc, self.dl, ctx)
                        if now < self.flash_until:
                            img = ImageOps.invert(img)     # full-screen white flash
                        data = to_mono_bytes(img)
                        # never re-send an identical frame: the LCD SDK round-trip is
                        # the most expensive thing left in the loop
                        if data != self._last_bitmap or now - self._last_submit > RESUBMIT_AFTER:
                            self.lcd.submit(data)
                            self._last_bitmap = data
                            self._last_submit = now

                if self.rgb:
                    self.rgb.update(st, self.page)

                time.sleep(UPDATE_INTERVAL)
            except Exception:
                # never let one bad tick kill the panel: an
                # UnboundLocalError once took the whole app down
                traceback.print_exc()
                time.sleep(1.0)

    def _check_buttons(self):
        """B1/B2 page, B3 status readout, B4 screen flash. Debounced."""
        now = time.time()
        cur = 0
        for b in (BTN_1, BTN_2, BTN_3, BTN_4):
            if self.lcd.button(b):
                cur |= b
        new = cur & ~self.prev_buttons
        self.prev_buttons = cur
        if not new or (now - self._btn_ts) < 0.15:
            return
        self._btn_ts = now

        if new & BTN_1:
            self.page = (self.page - 1) % len(self.pages)
        elif new & BTN_2:
            self.page = (self.page + 1) % len(self.pages)
        elif new & BTN_3:
            # STATUS: refresh OpenClaw and show the readout for a while
            threading.Thread(target=self._safe_poll, daemon=True).start()
            self.status_until = now + 5.0
        elif new & BTN_4:
            # FLASH: white flash + toggle the manual RGB alert
            self.flash_until = now + 0.7
            if self.rgb:
                self.rgb.manual_alert = not self.rgb.manual_alert
                if not self.rgb.manual_alert:
                    self.led.stop_effects()

    def _safe_poll(self):
        try:
            self.oc.poll()
        except Exception:
            pass

    def stop(self):
        self.running = False
        self.lcd.shutdown()
        self.led.shutdown()
        print("LCDGlance stopped.", flush=True)


if __name__ == "__main__":
    LCDGlance().start()
