# -*- coding: utf-8 -*-
"""Render every LCD page and mascot the way the real panel receives them.

This is the canonical screenshot generator for the README. It feeds each
page a realistic system state, binarises the canvas exactly like the G510
does (to_mono_bytes) and writes 4x nearest-neighbour PNGs into docs/screens/.

Usage:
    python preview.py            # writes docs/screens/*.png
    python preview.py --out DIR  # custom output directory

The filenames match the ones referenced from README.md, so regenerating the
docs is a single command and can never drift from the code again.
"""
import argparse
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

from src.util.constants import W, H, RGB_STATE
from src.render.bitmap import to_mono_bytes, mono_to_image
from src.render.gfx import Gfx
from src.mascots.mascot import MascotRenderer
from src.mascots.sources import build_sources, pick_active, mood_for, load_index
from src.anim.eventcard import EventCardManager
from src.anim.toast import ToastManager

from src.pages.now import NowPage
from src.pages.mascot import MascotPage
from src.pages.sources import SourcesPage
from src.pages.system import SystemPage
from src.pages.network import NetworkPage
from src.pages.openclaw_page import OpenClawPage
from src.pages.codex import CodexPage
from src.pages.activity import ActivityPage
from src.pages.alerts import AlertsPage
from src.pages.vps_page import VPSPage
from src.pages.download import DownloadPage
from src.pages.status import StatusPage
from src.pages.screensaver import ScreensaverPage
from src.pages.quickmenu import QuickMenuPage, DiagnosticsPage

# --- realistic sample state -----------------------------------------
NOW = time.time()
ST = {
    "cpu": 37.4, "cpu_freq": 2600,
    "mem": 62.1, "mem_used": 9.9, "mem_total": 16.0,
    "disk": 71.3, "disk_used": 664.0, "disk_total": 931.0,
    "net_up": 0.42, "net_dn": 3.8, "net_sent": 1234.0, "net_recv": 4321.0,
    "temps": [("Package id 0", 58.0)],
    "top": [{"name": "chrome", "cpu_percent": 24.0, "memory_percent": 12.0},
            {"name": "openclaw-wsl", "cpu_percent": 8.0, "memory_percent": 3.0},
            {"name": "LCore", "cpu_percent": 0.5, "memory_percent": 1.0}],
    "procs": 190, "uptime": 45678,
}

_HIST_CPU = [30 + 18 * math.sin(i / 6.0) + (i % 5) for i in range(60)]
_HIST_NET = [max(0.0, 0.4 + 0.35 * math.sin(i / 4.0) + 0.15 * math.sin(i / 1.7))
             for i in range(60)]
_HIST_RAM = [60 + 4 * math.sin(i / 9.0) for i in range(60)]
_HIST_DSK = [71.0 + 0.01 * i for i in range(60)]


class FakeOC:
    """OpenClaw monitor stand-in with a fully-populated snapshot."""

    def __init__(self, alerts=True):
        self.online = True
        self.running = 2
        self.ok, self.fail, self.total = 7, 2, 9
        self.last_task = "Widget - actualizaciones + legibilidad"
        self.last_task_status = "succeeded"
        self.last_poll_ok = NOW - 4
        self.last_event = None
        self.alerts = ([(NOW - 120, "ok", "DONE: SysGlance - profesionalizar"),
                        (NOW - 900, "fail", "FAIL: Visual defect inventory")]
                       if alerts else [])
        self.active_agents = {"research-agent": 1, "github-sync": 1}
        self.codex_seen = True
        self.codex_active = True
        self.codex_mtime = NOW - 8
        self.codex_last = "editing src/pages/system.py"
        self.state = "online"
        self.fail_count = 0
        self.latency = 0.42
        self.state_age = "12m"
        self.backoff = 1

    def snapshot(self):
        return dict(self.__dict__)


class FakeDL:
    """Download detector stand-in."""

    def __init__(self, active=False, state="idle"):
        self.active = active
        self.state = state
        self.name = "chrome"
        self.speed = 4.2
        self.peak = 6.1
        self.total_mb = 1234.0
        self.file = "ubuntu-26.04-desktop.iso"
        self.file_mb = 4340.0
        self.started = NOW - 180
        self._started = NOW - 180

    def snapshot(self):
        elapsed = (time.time() - self._started) if self.active else 0.0
        return {"active": self.active, "state": self.state, "name": self.name,
                "speed": self.speed, "peak": self.peak,
                "total_mb": self.total_mb, "file": self.file,
                "file_mb": self.file_mb, "elapsed": elapsed}


VPS_SNAP = {
    "enabled": True, "online": True, "host": "vps.smouj.dev",
    "cpu": 23.5, "ram": 48.2, "disk": 62.0, "uptime": "18d4h",
    "top_procs": [("nginx", 12.0), ("node", 9.0), ("postgres", 4.0)],
    "state": "online", "state_age": "12m", "fail_count": 0,
}

LCD_HEALTH = {"state": "online", "state_age": "41m", "latency": 0.0}
RGB_HEALTH = {"state": "online", "state_age": "41m", "latency": 0.0}


def build_ctx(gfx, mascot, oc, dl, busy=True, vps=VPS_SNAP):
    sources = build_sources(ST, oc, dl)
    active = pick_active(sources)
    return {
        "mascot": mascot, "sources": sources, "active_source": active,
        "mood": mood_for(ST, oc, dl, active), "load": load_index(ST, oc, dl),
        "busy": busy, "vps_snapshot": vps,
        "hist_bufs": {"cpu": _HIST_CPU, "ram": _HIST_RAM, "disk": _HIST_DSK},
        "anim_state": 10, "interaction": None, "interaction_trigger": None,
        "lcd_health": LCD_HEALTH, "rgb_health": RGB_HEALTH,
    }


class Shot:
    """Collects rendered panels and writes them to the output directory."""

    def __init__(self, out_dir):
        self.out = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.names = []

    def emit(self, name, img):
        """Binarise, save a 4x PNG, and return that same 4x image."""
        data = to_mono_bytes(img)
        back = mono_to_image(data).resize((W * 4, H * 4), Image.NEAREST)
        back.save(os.path.join(self.out, name + ".png"))
        self.names.append(name)
        return back


def main():
    ap = argparse.ArgumentParser(description="Generate LCD page screenshots")
    ap.add_argument("--out", default="docs/screens", help="output directory")
    args = ap.parse_args()

    gfx = Gfx()
    mascot = MascotRenderer(gfx)
    shot = Shot(args.out)

    # NetworkPage draws this module-level list directly; seed it for the shot.
    from src.sources.system import NET_HIST
    NET_HIST[:] = _HIST_NET

    oc_quiet = FakeOC(alerts=False)
    oc_busy = FakeOC(alerts=True)
    dl_idle = FakeDL(active=False)
    dl_active = FakeDL(active=True, state="active")

    ctx_busy = build_ctx(gfx, mascot, oc_busy, dl_idle, busy=True)
    ctx_idle = build_ctx(gfx, mascot, oc_quiet, dl_idle, busy=False)

    page_plan = [
        ("now", NowPage(), ctx_idle, 0),
        ("mascot-claw", MascotPage(), ctx_busy, 1),
        ("sources", SourcesPage(), ctx_busy, 2),
        ("system", SystemPage(), ctx_idle, 3),
        ("network", NetworkPage(), ctx_idle, 4),
        ("openclaw", OpenClawPage(), ctx_busy, 5),
        ("codex", CodexPage(), ctx_busy, 6),
        ("activity", ActivityPage(), ctx_busy, 7),
        ("alerts-clear", AlertsPage(), ctx_idle, 8),
    ]
    mosaic_imgs = []
    for name, page, ctx, idx in page_plan:
        img, d = gfx.canvas()
        gfx.dots = (idx, 10)
        RGB_STATE["effect"] = page.name.lower()
        page.render(gfx, d, ST, oc_busy, dl_idle, ctx)
        mosaic_imgs.append(shot.emit(name, img))

    st_alert = dict(ST, cpu=94.0, mem=92.0)
    img, d = gfx.canvas()
    gfx.dots = (8, 10)
    AlertsPage().render(gfx, d, st_alert, oc_busy, dl_idle, ctx_busy)
    shot.emit("alerts-active", img)

    img, d = gfx.canvas()
    gfx.dots = (9, 10)
    VPSPage().render(gfx, d, ST, oc_busy, dl_idle, ctx_busy)
    shot.emit("vps", img)

    # overlays and automatic pages
    img, d = gfx.canvas()
    gfx.dots = (0, 10)
    DownloadPage().render(gfx, d, ST, oc_busy, dl_active,
                          build_ctx(gfx, mascot, oc_busy, dl_active))
    shot.emit("download", img)

    img, d = gfx.canvas()
    StatusPage().render(gfx, d, ST, oc_busy, dl_idle, dict(ctx_busy, load=6824))
    shot.emit("overview", img)

    img, d = gfx.canvas()
    ScreensaverPage().render(gfx, d, ST, oc_quiet, dl_idle, ctx_idle)
    shot.emit("screensaver", img)

    qm = QuickMenuPage()
    qm.build_menu(ST, oc_busy, dl_idle, VPS_SNAP)
    img, d = gfx.canvas()
    qm.render(gfx, d, ST, oc_busy, dl_idle, ctx_busy)
    shot.emit("quickmenu", img)

    img, d = gfx.canvas()
    DiagnosticsPage().render(gfx, d, ST, oc_busy, dl_idle, ctx_busy)
    shot.emit("diagnostics", img)

    ec = EventCardManager()
    ec.push("ok", "BUILD COMPLETE", ["138 TESTS PASSED"], 2.5)
    img, d = gfx.canvas()
    ec.render(d, gfx, time.time())
    shot.emit("eventcard", img)

    tm = ToastManager()
    tm.push("AGENT OK: research-web", "ok", 3.0)
    img, d = gfx.canvas()
    MascotPage().render(gfx, d, ST, oc_busy, dl_idle, ctx_busy)
    tm.render(d, gfx, time.time())
    shot.emit("toast", img)

    # mascots, one per source
    for key in ("pc", "openclaw", "codex"):
        img, d = gfx.canvas()
        mascot.draw(d, key, 40, 21, "watch", busy=True)
        gfx.text(d, (86, 14), key.upper())
        gfx.text(d, (86, 26), "working", small=True)
        shot.emit("mascot-" + key, img)

    # hero: the three mascots together
    img, d = gfx.canvas()
    for i, key in enumerate(("pc", "openclaw", "codex")):
        mascot.draw(d, key, 30 + i * 50, 22, "watch", busy=(i != 0))
    gfx.text(d, (4, 2), "PC / CLAW / CODEX", small=True)
    shot.emit("hero-mascots", img)

    # mosaic: every navigable page stacked
    gap = 10
    w = max(i.width for i in mosaic_imgs)
    h = sum(i.height + gap for i in mosaic_imgs)
    sheet = Image.new("RGB", (w, h), (26, 26, 30))
    y = 0
    for i in mosaic_imgs:
        sheet.paste(i.convert("RGB"), (0, y))
        y += i.height + gap
    sheet.save(os.path.join(args.out, "pages-mosaic.png"))
    shot.names.append("pages-mosaic")

    print(f"wrote {len(shot.names)} screenshots to {args.out}/")
    for n in shot.names:
        print(f"  {n}.png")


if __name__ == "__main__":
    main()
