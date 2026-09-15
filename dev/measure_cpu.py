# -*- coding: utf-8 -*-
"""Restart lcdglance with the current code and measure its real CPU footprint."""
import subprocess, sys, os, time
import psutil

BASE = r"C:\Users\VersusPc\lcdglance"
print("restarting lcdglance...", flush=True)
subprocess.run([sys.executable, os.path.join(BASE, "launch_detached.py")],
               capture_output=True)
time.sleep(7)

target = None
for p in psutil.process_iter(["pid", "name", "cmdline"]):
    try:
        if (p.info["name"] or "").lower().startswith("pythonw"):
            cl = " ".join(p.info["cmdline"] or [])
            if "lcdglance.py" in cl:
                target = p
                break
    except Exception:
        continue
if target is None:
    print("!! lcdglance (pythonw) not found", flush=True)
    sys.exit(1)

proc = psutil.Process(target.pid)
print(f"pid {target.pid} up, sampling CPU for 12 s...", flush=True)
proc.cpu_percent(None)
time.sleep(12)
cpu = proc.cpu_percent(None)
rss = proc.memory_info().rss / (1024 ** 2)
print(f"\n  lcdglance CPU over 12 s : {cpu:6.2f} %  (of one core)", flush=True)
print(f"  lcdglance RSS          : {rss:6.1f} MB", flush=True)
syscpu = psutil.cpu_percent(interval=1)
print(f"  system CPU (1 s)       : {syscpu:6.1f} %", flush=True)
print(f"  cpu count              : {psutil.cpu_count()}", flush=True)
