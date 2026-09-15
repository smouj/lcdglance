# -*- coding: utf-8 -*-
"""Exercise every code path that runs in the real loop, and time the cache."""
import sys, os, time
sys.path.insert(0, r"C:\Users\VersusPc\lcdglance")
import lcdglance as L
from PIL import Image

print("=== smoke test ===", flush=True)
print("font:", L.Gfx().font, flush=True)
print(f"W={L.W} H={L.H} BITMAP_SIZE={L.BITMAP_SIZE} thr={L.BIN_THRESHOLD}", flush=True)
assert L.BITMAP_SIZE == 6880, "bitmap size must be 160*43"

class FakeOC:
    def __init__(self):
        self.online, self.running, self.ok, self.fail = True, 0, 7, 2
        self.last_task, self.last_task_status = "Widget - pruebas", "succeeded"
        self.last_poll_ok = time.time() - 4
        self.last_event = None
        self.alerts = [(time.time() - 120, "ok", "DONE: SysGlance"),
                       (time.time() - 900, "fail", "FAIL: defectos")]
        self.active_agents = {}
        self.codex_seen, self.codex_active = True, False
        self.codex_mtime, self.codex_last = time.time() - 600, "s.jsonl"
    def snapshot(self):
        return dict(self.__dict__)

class FakeDL:
    def __init__(self):
        self.active, self.name, self.speed, self.peak = True, "chrome", 4.2, 6.1
        self.total_mb, self.file, self.file_mb = 1234.0, "ubuntu.iso", 1234.0
        self.started = time.time() - 180
    def snapshot(self):
        return {"active": self.active, "name": self.name, "speed": self.speed,
                "peak": self.peak, "total_mb": self.total_mb, "file": self.file,
                "file_mb": self.file_mb, "elapsed": time.time() - self.started}

gfx = L.Gfx(); mascot = L.MascotRenderer(gfx)
gfx.dots = (0, 8)
oc, dl = FakeOC(), FakeDL()

print("\n--- stats cache timing ---", flush=True)
for i in range(4):
    a = time.perf_counter(); st = L.get_system_stats(); dt = (time.perf_counter()-a)*1000
    print(f"  call {i+1}: {dt:7.2f} ms", flush=True)
print("  top procs:", [p["name"] for p in (st.get("top") or [])], flush=True)
time.sleep(3.2)
a = time.perf_counter(); L.get_system_stats(); print(f"  after 3.2s (top refresh): {(time.perf_counter()-a)*1000:7.2f} ms", flush=True)

sources = L.build_sources(st, oc, dl)
active = L.pick_active(sources)
print("\n--- sources ---", flush=True)
for s in sources:
    print(f"  {s['label']:6s} online={str(s['online']):5s} busy={str(s['busy']):5s} {s['detail']}", flush=True)
print("  featured:", active["label"], "mood:", L.mood_for(st, oc, dl, active), flush=True)

ctx = {"mascot": mascot, "sources": sources, "active_source": active,
       "mood": L.mood_for(st, oc, dl, active)}

print("\n--- render every page + convert ---", flush=True)
pages = [L.MascotPage(), L.SourcesPage(), L.SystemPage(), L.NetworkPage(),
         L.ProcsPage(), L.OpenClawPage(), L.AlertsPage(), L.DownloadPage()]
tot = 0.0
for p in pages:
    n = 12
    a = time.perf_counter()
    for _ in range(n):
        img, d = gfx.canvas()
        p.render(gfx, d, st, oc, dl, ctx)
        data = L.to_mono_bytes(img)
    dt = (time.perf_counter() - a) / n * 1000
    tot += dt
    assert len(data) == 6880, f"{p.name}: bad buffer {len(data)}"
    print(f"  {p.name:9s} {dt:6.2f} ms/frame", flush=True)
print(f"\n  AVG {tot/len(pages):.2f} ms  =>  {1000/(tot/len(pages)):.0f} fps headroom", flush=True)

# mascots
for k in ("openclaw", "codex", "pc"):
    for mood in ("idle", "watch", "happy", "worried", "alarm", "focus"):
        img, d = gfx.canvas()
        mascot.draw(d, k, 30, 21, mood)
        mascot.draw_mini(d, k, 20, 15, True)
        assert len(L.to_mono_bytes(img)) == 6880
print("  all mascots x moods x sizes OK", flush=True)
print("\n=== SMOKE PASSED ===", flush=True)
