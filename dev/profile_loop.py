# -*- coding: utf-8 -*-
"""Attribute the loop's CPU time to its components, for 10 s of real cadence."""
import sys, os, time
sys.path.insert(0, r"C:\Users\VersusPc\lcdglance")
import lcdglance as L
from PIL import Image

gfx = L.Gfx(); mascot = L.MascotRenderer(gfx)
oc = L.OpenClawMonitor()          # no polling: we measure the loop only
dl = L.DownloadDetector()
st = L.get_system_stats()
sources = L.build_sources(st, oc, dl)
active = L.pick_active(sources)
ctx = {"mascot": mascot, "sources": sources, "active_source": active,
       "mood": L.mood_for(st, oc, dl, active)}
page = L.SystemPage()

acc = {}
def add(k, a):
    acc[k] = acc.get(k, 0.0) + (time.process_time() - a)

frames = 0
t0 = time.process_time(); w0 = time.time()
next_stats = next_dl = 0.0
while time.time() - w0 < 10:
    a = time.process_time(); st = L.get_system_stats(); add("stats", a)
    a = time.process_time()
    sources = L.build_sources(st, oc, dl); active = L.pick_active(sources)
    ctx["mood"] = L.mood_for(st, oc, dl, active); ctx["sources"] = sources
    ctx["active_source"] = active
    add("sources+mood", a)
    a = time.process_time()
    img, d = gfx.canvas(); page.render(gfx, d, st, oc, dl, ctx)
    L.page_marker(d, 0, 7); data = L.to_mono_bytes(img)
    add("render+convert", a)
    a = time.process_time(); dl.poll(st); add("download poll", a)
    frames += 1
    time.sleep(0.25)

cpu = time.process_time() - t0
wall = time.time() - w0
print(f"frames={frames}  cpu={cpu:.2f}s  wall={wall:.2f}s", flush=True)
print(f"\n  TOTAL python CPU: {cpu/wall*100:.2f} % of one core\n", flush=True)
for k, v in sorted(acc.items(), key=lambda x: -x[1]):
    print(f"    {k:18s} {v/wall*100:6.2f} %", flush=True)
print(f"\n  (remaining {cpu/wall*100 - sum(acc.values())/wall*100:.2f} % = loop overhead)", flush=True)
