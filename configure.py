# -*- coding: utf-8 -*-
"""Leave ONLY the correct LCDGlance applet registered in LGS and apply it.

Removes stale/duplicate registrations created while testing
(LCDGlanceDiag, LCDGlanceTest, and the LCDGlance variant registered under a
different python executable), disables every built-in applet on both the G510
and the mono emulator, pins the foreground applet and disables auto-rotation.

Run with LGS stopped: LGS rewrites settings.json on exit.
"""
import json, os, shutil, subprocess, sys, time

BASE = r"C:\Users\VersusPc\AppData\Local\Logitech\Logitech Gaming Software"
SETTINGS = os.path.join(BASE, "settings.json")
BACKUP = os.path.join(BASE, "settings.json.lcdglance-preconfig")
LGS_EXE = r"C:\Program Files\Logitech Gaming Software\LCore.exe"
LAUNCHER = r"C:\Users\VersusPc\lcdglance\launch_detached.py"
CREATE_NO_WINDOW = 0x08000000

KEEP_NAME = "LCDGlance"
DROP_NAMES = {"LCDGlanceDiag", "LCDGlanceTest", "LCDGlanceCalib"}

print("=== LGS LCD config normalisation ===\n", flush=True)

print("1. Stopping LGS...", flush=True)
for exe in ("LCore.exe", "RestartLCore.exe"):
    subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True)
time.sleep(3)

if not os.path.exists(BACKUP):
    shutil.copy2(SETTINGS, BACKUP)
    print(f"   backup -> {BACKUP}", flush=True)

with open(SETTINGS, "r", encoding="utf-8") as f:
    cfg = json.load(f)

lcd = cfg.setdefault("lcd", {})
applets = lcd.setdefault("applets", {})
devices = lcd.setdefault("devices", {})

# pick the single id to keep: named LCDGlance, started via pythonw.exe
keep_id = None
for aid, meta in applets.items():
    if (meta.get("name") or "") == KEEP_NAME and \
            "pythonw.exe" in (meta.get("appPath") or "").lower():
        keep_id = aid
        break
if keep_id is None:
    for aid, meta in applets.items():
        if (meta.get("name") or "") == KEEP_NAME:
            keep_id = aid
            break
if keep_id is None:
    print("[!] no LCDGlance applet registered; aborting", flush=True)
    sys.exit(1)
print(f"\n2. Keeping applet {keep_id} -> {applets[keep_id].get('appPath')}", flush=True)

removed = []
for aid in list(applets.keys()):
    name = applets[aid].get("name") or ""
    path = (applets[aid].get("appPath") or "").lower()
    stale = (name in DROP_NAMES) or (name == KEEP_NAME and aid != keep_id) \
            or ("python3.13.exe" in path and aid != keep_id)
    if stale:
        del applets[aid]
        removed.append(f"{aid}({name})")
print("   removed catalogue entries:", removed or "none", flush=True)

for dev, dcfg in devices.items():
    da = dcfg.setdefault("applets", {})
    for aid in list(da.keys()):
        if aid not in applets:
            del da[aid]
    for aid in list(da.keys()):
        da[aid] = {"enabled": aid == keep_id}
    da[keep_id] = {"enabled": True}
    dcfg["foregroundapplet"] = keep_id
    dcfg["switchmethod"] = 0
    enabled = [a for a, s in da.items() if s.get("enabled")]
    print(f"   [{dev}] fg={keep_id} switch=0 enabled={enabled}", flush=True)

applets[keep_id]["autostartable"] = False
applets[keep_id]["format"] = 0

prof = cfg.setdefault("profiler", {})
prof["showProfileActivationOnLCD"] = False
prof["showQuickMacrosOnLCD"] = False
prof["showMacroActivationOnLCD"] = False
cfg.setdefault("notification", {})["showDPIChangeOnLCD"] = False

with open(SETTINGS, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print("\n3. settings.json written", flush=True)

print("4. Starting LGS...", flush=True)
subprocess.Popen([LGS_EXE], creationflags=CREATE_NO_WINDOW)
time.sleep(14)

print("5. Restarting lcdglance...", flush=True)
subprocess.run([sys.executable, LAUNCHER], capture_output=True)
time.sleep(5)

print("\n6. Verification", flush=True)
with open(SETTINGS, "r", encoding="utf-8") as f:
    after = json.load(f)
al = after.get("lcd", {}).get("applets", {})
print(f"   applets registered: {len(al)}", flush=True)
for aid, meta in al.items():
    print(f"     {aid}: {meta.get('name')}", flush=True)
for dev, dcfg in (after.get("lcd", {}).get("devices") or {}).items():
    en = [a for a, s in (dcfg.get("applets") or {}).items() if s.get("enabled")]
    print(f"   [{dev}] fg={dcfg.get('foregroundapplet')} sw={dcfg.get('switchmethod')} enabled={en}", flush=True)

r = subprocess.run(["tasklist"], capture_output=True, text=True)
for l in r.stdout.splitlines():
    if any(k in l.lower() for k in ["pythonw", "lcore", "lcdmedia"]):
        print("   proc:", l.strip(), flush=True)
print("\n=== done ===", flush=True)
