"""Launch LCDGlance detached (survives console close) and kill stale instances."""
import os, sys, time, subprocess

LCD_DIR = r"C:\Users\VersusPc\lcdglance"
SCRIPT = os.path.join(LCD_DIR, "lcdglance.py")
LOG = os.path.join(LCD_DIR, "lcdglance.log")

PYTHONW = r"C:\Users\VersusPc\AppData\Local\Programs\Python\Python313\pythonw.exe"
if not os.path.exists(PYTHONW):
    PYTHONW = r"C:\Users\VersusPc\AppData\Local\Microsoft\WindowsApps\pythonw.exe"
if not os.path.exists(PYTHONW):
    PYTHONW = sys.executable

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

print("launcher: pythonw =", PYTHONW, flush=True)

# 1) kill LGS LCD applets that steal the screen
for n in ("LCDMedia.exe", "LCDClock.exe", "LCDPop3.exe", "LCDRSS.exe",
          "LCDYouTube.exe", "LCDCountdown.exe"):
    subprocess.run(["taskkill", "/F", "/IM", n],
                   capture_output=True, creationflags=CREATE_NO_WINDOW)

# 2) kill previous lcdglance instances only (cmdline mentions lcdglance.py)
killed = []
try:
    import psutil
    me = os.getpid()
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if p.info["pid"] == me:
                continue
            nm = (p.info["name"] or "").lower()
            if not nm.startswith("python"):
                continue
            cl = " ".join(p.info["cmdline"] or [])
            if "lcdglance.py" in cl and "launch_detached" not in cl:
                p.kill()
                killed.append(p.info["pid"])
        except Exception:
            pass
except Exception as e:
    print("psutil unavailable:", e, flush=True)

print("killed previous:", killed, flush=True)
time.sleep(1)

# 3) launch detached
log = open(LOG, "a", encoding="utf-8", errors="replace")
proc = subprocess.Popen(
    [PYTHONW, SCRIPT],
    stdout=log, stderr=log, stdin=subprocess.DEVNULL,
    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    close_fds=True,
)
print("LAUNCHED_PID", proc.pid, flush=True)
