# -*- coding: utf-8 -*-
"""Render every LCD page + all mascots the way the panel receives them."""
import sys, os, math, time
sys.path.insert(0, r"C:\Users\VersusPc\lcdglance")
import lcdglance as L
from PIL import Image

gfx = L.Gfx()
mascot = L.MascotRenderer(gfx)

st = {"cpu": 37.4, "cpu_freq": 2600, "mem": 62.1, "mem_used": 9.9, "mem_total": 16.0,
      "disk": 71.3, "disk_used": 664.0, "disk_total": 931.0,
      "net_up": 0.42, "net_dn": 3.8, "net_sent": 1234.0, "net_recv": 4321.0,
      "temps": [("Package id 0", 58.0)],
      "top": [{"name": "chrome", "cpu_percent": 24.0, "memory_percent": 12.0},
              {"name": "openclaw-wsl", "cpu_percent": 8.0, "memory_percent": 3.0},
              {"name": "LCore", "cpu_percent": 0.5, "memory_percent": 1.0}],
      "procs": 190, "uptime": 45678}
L.NET_HIST[:] = [abs(60 * math.sin(i / 5.0)) + 4 for i in range(60)]


class FakeOC:
    def __init__(self):
        self.online, self.running, self.ok, self.fail = True, 0, 7, 2
        self.last_task = "Widget - actualizaciones + legibilidad"
        self.last_task_status = "succeeded"
        self.last_poll_ok = time.time() - 4
        self.last_event = None
        self.alerts = [(time.time() - 120, "ok", "DONE: SysGlance - profesionalizar"),
                       (time.time() - 900, "fail", "FAIL: Visual defect inventory")]
        self.active_agents = {}
        self.codex_seen = True
        self.codex_active = False
        self.codex_mtime = time.time() - 600
        self.codex_last = "session.jsonl"

    def snapshot(self):
        return dict(self.__dict__)


class FakeDL:
    def __init__(self):
        self.active, self.name, self.speed, self.peak = False, "chrome", 4.2, 6.1
        self.total_mb, self.file, self.file_mb = 1234.0, "ubuntu-24.04-desktop.iso", 1234.0
        self.started = time.time() - 180

    def snapshot(self):
        return {"active": self.active, "name": self.name, "speed": self.speed,
                "peak": self.peak, "total_mb": self.total_mb, "file": self.file,
                "file_mb": self.file_mb, "elapsed": time.time() - self.started}


oc, dl = FakeOC(), FakeDL()
out = r"C:\Users\VersusPc\lcdglance\preview"
os.makedirs(out, exist_ok=True)
panels = []


def emit(name, img):
    data = L.to_mono_bytes(img)
    back = L.mono_to_image(data)
    back.resize((L.W * 4, L.H * 4), Image.NEAREST).save(os.path.join(out, name + ".png"))
    panels.append(name + ".png")


sources = L.build_sources(st, oc, dl)
active = L.pick_active(sources)
power = L.load_index(st, oc, dl)
gfx.dots = (0, 7)
ctx = {"mascot": mascot, "sources": sources, "active_source": active,
       "mood": L.mood_for(st, oc, dl, active), "load": power, "busy": True}
for p in [L.MascotPage(), L.SourcesPage(), L.SystemPage(), L.NetworkPage(),
          L.ProcsPage(), L.OpenClawPage(), L.AlertsPage(), L.DownloadPage(),
          L.StatusPage()]:
    img, d = gfx.canvas()
    L.RGB_STATE["effect"] = "mascot"
    p.render(gfx, d, st, oc, dl, ctx)
    emit("p_" + p.name.lower(), img)

# every mascot x every mood, idle and busy
for key in ("openclaw", "codex", "pc"):
    for mood in ("idle", "watch", "happy", "worried", "alarm", "focus"):
        img, d = gfx.canvas()
        mascot.draw(d, key, 26, 21, mood, busy=(mood in ("watch", "alarm")))
        gfx.text(d, (56, 2), f"{key.upper()}")
        gfx.text(d, (56, 16), mood, small=True)
        emit(f"m_{key}_{mood}", img)

imgs = [Image.open(os.path.join(out, n)) for n in panels]
sheet = Image.new("RGB", (imgs[0].width, sum(i.height + 8 for i in imgs)), (30, 30, 30))
y = 0
for i in imgs:
    sheet.paste(i.convert("RGB"), (0, y))
    y += i.height + 8
sheet.save(os.path.join(out, "_sheet.png"))
print("panels:", len(panels))
