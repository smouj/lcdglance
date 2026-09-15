# -*- coding: utf-8 -*-
"""Sample the ALREADY RUNNING lcdglance process (no restart, no startup burst)."""
import sys, time, psutil

target = None
for p in psutil.process_iter(["pid", "name", "cmdline"]):
    try:
        if (p.info["name"] or "").lower().startswith("pythonw"):
            if "lcdglance.py" in " ".join(p.info["cmdline"] or []):
                target = p
                break
    except Exception:
        continue
if target is None:
    print("lcdglance not running")
    sys.exit(1)

proc = psutil.Process(target.pid)
proc.cpu_percent(None)
print(f"pid {target.pid}: settling 25 s, then measuring 30 s...", flush=True)
time.sleep(25)
proc.cpu_percent(None)
time.sleep(30)
cpu = proc.cpu_percent(None)
rss = proc.memory_info().rss / (1024 ** 2)
syscpu = psutil.cpu_percent(interval=2)
print(f"\n  lcdglance CPU (steady state, 30 s window): {cpu:6.2f} % of one core")
print(f"  lcdglance RSS                            : {rss:6.1f} MB")
print(f"  system CPU during sample                 : {syscpu:6.1f} % of {psutil.cpu_count()} cores")
print(f"  => as a share of the whole machine       : {cpu / psutil.cpu_count():6.2f} %")
