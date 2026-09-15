"""Physical and timing constants for the G510 160×43 mono LCD."""

import os

# ─── LCD dimensions ────────────────────────────────────────────────
W, H = 160, 43
BITMAP_SIZE = W * H  # 6880 bytes, one byte per pixel (not packed 1-bpp)

# ─── Logitech SDK constants ────────────────────────────────────────
LOGI_LCD_TYPE_MONO = 0x00000001
BTN_1, BTN_2, BTN_3, BTN_4 = 0x01, 0x02, 0x04, 0x08

# ─── LGS paths ─────────────────────────────────────────────────────
LGS_DIR = r"C:\Program Files\Logitech Gaming Software"
LCD_DLL_PATH = os.path.join(LGS_DIR, "SDK", "LCD", "x64", "LogitechLcd.dll")
LED_DLL_PATH = os.path.join(LGS_DIR, "SDK", "LED", "x64", "LogitechLed.dll")

# ─── Timing intervals (seconds) ───────────────────────────────────
LOOP_INTERVAL     = 0.10    # main loop tick — fast enough for 12 FPS when animated
RENDER_MIN_GAP    = 0.06    # minimum gap between renders (~16 FPS ceiling)
RESUBMIT_AFTER   = 5.0     # re-send unchanged frame to protect against LGS reset
LCD_RECONNECT    = 5.0     # how often to check LCD connection
OC_POLL_INTERVAL = 15.0    # OpenClaw probe interval
DL_POLL_INTERVAL = 1.0     # download detector interval
VPS_POLL_DEFAULT = 30.0    # VPS SSH poll interval
APP_KILL_INTERVAL= 300.0  # sweep LGS applets every 5 min

# ─── Animation FPS by state ────────────────────────────────────────
FPS_IDLE      = 4    # mascot idle, static data pages
FPS_ANIMATED  = 8    # mascot watch/happy, data pages with sparklines
FPS_BUSY      = 12   # mascot alarm, download, transitions
FPS_TRANSITION= 24   # page transitions (brief burst)

# ─── Download detector thresholds ─────────────────────────────────
DL_MIN_GROWTH_MB = 0.30
DL_MIN_NET_MB    = 0.15
DL_MIN_STREAK    = 4
DL_MIN_TOTAL_MB  = 3.0
DL_QUIET_STOP    = 12

# ─── OpenClaw task statuses ────────────────────────────────────────
TERMINAL_OK  = {"succeeded"}
TERMINAL_BAD = {"failed", "timed_out", "cancelled", "lost"}
RUNTIME_TAG  = {"subagent": "AGENT", "cron": "AUTO", "acp": "CODEX", "cli": "CLI"}

# ─── RGB colour tables ────────────────────────────────────────────
LOAD_PALETTE = [
    (0.00, (5, 18, 70)),   (0.30, (0, 70, 95)),
    (0.55, (10, 90, 45)),  (0.75, (95, 70, 0)),
    (1.00, (100, 12, 12)),
]
PAGE_THEME = {
    0: None,             # Mascot  → active source colour
    1: (70, 60, 90),     # Sources → slate
    2: None,             # System  → CPU gradient
    3: (0, 65, 90),      # Network → teal
    4: (60, 25, 95),     # Procs   → violet
    5: (0, 80, 95),      # OpenClaw → cyan
    6: (95, 60, 0),      # Alerts  → amber
    7: (0, 60, 80),      # VPS     → dark teal
}
MASCOT_COLOR = {
    "pc":       (0, 70, 95),    # blue
    "openclaw": (0, 88, 92),    # cyan
    "codex":    (15, 92, 48),   # green
}
ACTIVE_COLOR = (95, 80, 0)     # highlight while a source is busy
FLASH_COLOR  = (0, 60, 100)    # download / transfer accent
MASCOT_NAME  = {"pc": "PC", "openclaw": "CLAW", "codex": "CODEX"}

# ─── Rendering switches ────────────────────────────────────────────
INVERT        = False    # True → swap lit/unlit pixels
BIN_THRESHOLD = 120      # luminance cutoff: 128 loses strokes, 100 merges 'm'

# Sprite mascots (pixel-art bitmaps in mascots/sprites.py) are OPT-IN.
# On the real G510 panel the hand-drawn procedural mascots read better:
# sprites alias badly at 1-bit on a 160x43 mono display. The sprite path
# stays available behind this flag and MascotRenderer falls back to the
# procedural renderer whenever sprites are off or lack a key+mood.
USE_SPRITES   = False

# ─── Download directories to watch ─────────────────────────────────
DL_DIRS = [
    os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam", "steamapps", "downloading"),
    os.path.join(os.environ.get("ProgramFiles", ""), "Steam", "steamapps", "downloading"),
]
DL_HINTS = (
    "chrome", "msedge", "firefox", "brave", "opera", "vivaldi",
    "steam", "curl", "wget", "aria2", "qbittorrent", "transmission",
    "idman", "battle.net", "epicgames", "origin", "eaapp", "gog", "uplay", "ubisoft",
)

# ─── Paths ──────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEN_FILE        = os.path.join(HERE, "oc_seen.json")
VPS_CONFIG_FILE  = os.path.join(HERE, "vps_config.json")
WSL_CMD = ["wsl.exe", "-d", "Ubuntu-24.04", "-e", "bash", "-lc", "lcd-probe"]
CREATE_NO_WINDOW  = 0x08000000

# ─── Process filter ────────────────────────────────────────────────
SKIP_PROCS = {"", "system idle process", "system", "idle", "memory compression"}

# ─── Shared mutable state ──────────────────────────────────────────
# RGB_STATE is a shared dict between RGBEngine and AlertsPage for the
# current RGB effect label. It lives here so both modules can import it
# without circular dependencies.
RGB_STATE = {"effect": "-"}
