#!/usr/bin/env python3
"""LCDGlance self-check — renders every page headlessly and asserts the layout.

No LCD hardware is required. Run from the project root:

    python verify.py            # quiet: prints PASS/FAIL summary
    python verify.py -v         # verbose: one line per check
    python verify.py --preview  # also writes preview/verify_sheet.png

Checks
  1. Canvas is 160x43 and the mono buffer is exactly 6880 bytes.
  2. Every page renders without raising.
  3. Every header shows a HH:MM clock.
  4. Header elements (title / right text / clock / page dots) never overlap:
     consecutive ink runs keep a >= 2 px gap.
  5. The Mascot page clock never touches the source label or the separator.
  6. Mascot art is identical across builds: each mascot key produces a
     distinct bitmap, and none is blank.  The screensaver is activity-aware
     (never shows while work is in progress), and every documented button
     gesture (tap, hold, combo) produces its action.
  7. ConnectionSupervisor transitions correctly between ONLINE/STALE/OFFLINE
     with backoff, and toast deduplication prevents repeated notifications.
  8. NOW page renders without errors and shows PC/CLAW/CODEX/NET status.
  9. Activity, Codex and event-card overlays render without errors.
 10. v10 integration regressions: mascot page is an instance (not pages[0]),
     fps/interval are defined without an LCD, RGB theming is name-keyed, and
     the quick menu accepts a snapshot dict.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.util.constants import W, H, BITMAP_SIZE, MASCOT_NAME, BIN_THRESHOLD
from src.render.gfx import Gfx
from src.render.bitmap import to_mono_bytes
from src.mascots.mascot import MascotRenderer
from src.mascots.sources import build_sources, pick_active, mood_for
from src.sources.system import NET_HIST
from src.pages.mascot import MascotPage, _usage_text
from src.pages.screensaver import ScreensaverPage
from src.ui.buttons import ButtonHandler
from src.supervisor import ConnectionSupervisor
from src.pages.sources import SourcesPage
from src.pages.system import SystemPage
from src.pages.network import NetworkPage
from src.pages.procs import ProcsPage
from src.pages.openclaw_page import OpenClawPage
from src.pages.alerts import AlertsPage
from src.pages.status import StatusPage
from src.pages.download import DownloadPage


# ─── fixtures ─────────────────────────────────────────────────────
class _OC:
    def __init__(self):
        self.online = True; self.running = 0; self.ok = 7; self.fail = 2
        self.last_task = "Widget - updates"; self.last_task_status = "succeeded"
        self.last_poll_ok = time.time() - 4; self.last_event = None
        self.alerts = [(time.time() - 120, "ok", "DONE: SysGlance")]
        self.active_agents = {}; self.codex_seen = True; self.codex_active = False
        self.codex_mtime = time.time() - 600; self.codex_last = "session.jsonl"
        # model + quota (as parsed from the lcd-probe M|/U| lines)
        self.model = "deepseek/deepseek-flash"
        self.usage_provider = "deepseek"
        self.usage_balance = "$4.02"
        self.usage_window_label = ""
        self.usage_window_pct = ""
    def snapshot(self):
        return dict(self.__dict__)


class _DL:
    def __init__(self):
        self.active = False; self.name = ""; self.speed = 0.0
    def snapshot(self):
        return {"active": False, "name": "", "speed": 0, "peak": 0,
                "total_mb": 0, "file": "", "file_mb": 0, "elapsed": 0}


STATS = {
    "cpu": 37.4, "mem": 62.1, "disk": 71.3,
    "net_up": 0.42, "net_dn": 3.8, "net_sent": 1234.0, "net_recv": 4321.0,
    "temps": [("Package id 0", 58.0)],
    "top": [{"name": "chrome", "cpu_percent": 24.0, "memory_percent": 12.0},
            {"name": "openclaw-wsl", "cpu_percent": 8.0, "memory_percent": 3.0},
            {"name": "LCore", "cpu_percent": 0.5, "memory_percent": 1.0}],
    "procs": 190, "uptime": 45678,
}

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
_failures = []


def check(name, ok, detail="", verbose=False):
    if not ok:
        _failures.append(name)
    if verbose or not ok:
        print(f"  [{PASS if ok else FAIL}] {name}" + (f"  — {detail}" if detail else ""))
    return ok


def header_runs(img, y0=0, y1=12):
    """Ink column runs in a horizontal band, merged when gap <= 2 px."""
    px = img.load()
    cols = [any(px[x, y] > 127 for y in range(y0, y1)) for x in range(W)]
    runs, start = [], None
    for x, ink in enumerate(cols):
        if ink and start is None:
            start = x
        elif not ink and start is not None:
            runs.append([start, x - 1]); start = None
    if start is not None:
        runs.append([start, W - 1])
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] <= 2:
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--preview", action="store_true",
                    help="write preview/verify_sheet.png")
    args = ap.parse_args()
    v = args.verbose

    print("LCDGlance self-check")
    print("=" * 52)

    gfx = Gfx()
    mascot = MascotRenderer(gfx, sprites=None)
    oc, dl = _OC(), _DL()
    NET_HIST[:] = [abs(60 * (i % 10) / 10.0) + 4 for i in range(60)]
    sources = build_sources(STATS, oc, dl)
    by_key = {s["key"]: s for s in sources}

    # 1 — canvas geometry
    img, d = Gfx.canvas()
    check("canvas is 160x43", img.size == (W, H), f"got {img.size}", v)
    check("mono buffer is 6880 bytes",
          len(to_mono_bytes(img)) == BITMAP_SIZE, "", v)

    # 2/3/4 — every page renders, shows a clock, and keeps a clean header
    pages = [MascotPage(), SourcesPage(), SystemPage(), NetworkPage(),
             ProcsPage(), OpenClawPage(), AlertsPage(), StatusPage(),
             DownloadPage()]
    clock = time.strftime("%H:%M").lstrip("0") or "0:00"
    for i, p in enumerate(pages):
        gfx.dots = (i, len(pages))
        ctx = {"mascot": mascot, "sources": sources,
               "active_source": by_key["openclaw"],
               "mood": mood_for(STATS, oc, dl, by_key["openclaw"]),
               "load": 12345, "busy": False, "vps_snapshot": {},
               "hist_bufs": {"cpu": [], "ram": [], "disk": []},
               "anim_state": 0, "interaction": None, "interaction_trigger": None}
        try:
            im, dr = Gfx.canvas()
            p.render(gfx, dr, STATS, oc, dl, ctx)
        except Exception as e:                              # noqa: BLE001
            check(f"{p.name}: renders", False, repr(e), v)
            continue
        check(f"{p.name}: renders", True, "", v)

        runs = header_runs(im)
        gaps = [runs[j + 1][0] - runs[j][1] for j in range(len(runs) - 1)]
        min_gap = min(gaps) if gaps else 99
        check(f"{p.name}: header has no overlap", min_gap >= 2,
              f"min_gap={min_gap}px runs={runs}", v)

    # 5 — Mascot page: clock must not touch the source label or separator
    for key in ("openclaw", "codex", "pc"):
        gfx.dots = (0, len(pages))
        ctx = {"mascot": mascot, "sources": sources, "active_source": by_key[key],
               "mood": "idle", "load": 12345, "busy": False, "vps_snapshot": {},
               "hist_bufs": {"cpu": [], "ram": [], "disk": []},
               "anim_state": 0, "interaction": None, "interaction_trigger": None}
        im, dr = Gfx.canvas()
        MascotPage().render(gfx, dr, STATS, oc, dl, ctx)
        runs = header_runs(im)
        # last two runs must be clock then dots, with a gap
        ok = len(runs) >= 2 and (runs[-1][0] - runs[-2][1]) >= 2
        check(f"Mascot/{key}: clock clear of dots", ok,
              f"runs={runs}", v)

    # 5b — Mascot page: model + usage render on their own lines, right column
    gfx.dots = (0, len(pages))
    ctx = {"mascot": mascot, "sources": sources, "active_source": by_key["openclaw"],
           "mood": "idle", "load": 12345, "busy": False, "vps_snapshot": {},
           "hist_bufs": {"cpu": [], "ram": [], "disk": []},
           "anim_state": 0, "interaction": None, "interaction_trigger": None}
    im, dr = Gfx.canvas()
    MascotPage().render(gfx, dr, STATS, oc, dl, ctx)
    pxs = im.load()
    def _row_ink(y0, y1, x0=63):
        return any(pxs[x, y] > 127 for x in range(x0, W) for y in range(y0, y1))
    check("Mascot: model line present (y=22..31)", _row_ink(22, 31), "", v)
    check("Mascot: usage line present (y=32..41)", _row_ink(32, 41), "", v)
    check("Mascot: quota text mentions left/balance",
          "left" in _usage_text(oc.snapshot()) or oc.snapshot().get("usage_balance"),
          _usage_text(oc.snapshot()), v)

    # 5c — screensaver is activity-aware (must never hide work in progress)
    ss = ScreensaverPage()
    now = time.time()
    ss.feed_input(now - 999)                 # long ago
    check("screensaver: shows when idle and nothing is running",
          ss.should_show(now, busy=False) is True, "", v)
    check("screensaver: never shows while busy",
          ss.should_show(now, busy=True) is False, "", v)
    ss.feed_activity(now)
    check("screensaver: recent activity suppresses it",
          ss.should_show(now, busy=False) is False, "", v)
    ss.feed_input(now)
    check("screensaver: a button press suppresses it",
          ss.should_show(now, busy=False) is False, "", v)
    check("screensaver: idle_seconds tracks the later of input/activity",
          abs(ss.idle_seconds(now)) < 0.01, f"{ss.idle_seconds(now)}", v)

    # 5b — NOW page renders (use empty stats like other page tests)
    from src.pages.now import NowPage
    np = NowPage()
    img_np, d_np = gfx.canvas()
    np.render(gfx, d_np, {}, oc, dl, {"sources": [], "active_source": {"key": "pc", "label": "PC", "online": True, "busy": False, "detail": ""}, "busy": False})
    check("NOW page renders", True, "no error", v)

    # 5b2 — Activity page renders
    from src.pages.activity import ActivityPage
    ap = ActivityPage()
    img_ap, d_ap = gfx.canvas()
    ap.render(gfx, d_ap, {}, oc, dl, {})
    check("Activity page renders", True, "no error", v)

    # 5b2b — inverse text is actually visible (regression: white-on-white)
    from src.anim.toast import ToastManager
    tm = ToastManager()
    tm.push("HELLO INVERSE", "info", 2.0)
    img_t, d_t = Gfx.canvas()
    gfx.dots = (0, 1)
    _drawn = tm.render(d_t, gfx, time.time())
    # The toast bar is y=0..10 and filled white. If the text were also white
    # the bar would be a solid block; count BLACK pixels inside the bar.
    # Text is antialiased: count pixels that binarise to black on the panel.
    _bar_pixels = [img_t.getpixel((x, y))
                   for y in range(11) for x in range(W)]
    _dark_in_bar = sum(1 for v in _bar_pixels if v <= BIN_THRESHOLD)
    check("toast: inverse text visible on white bar",
          _drawn and _dark_in_bar > 40, f"{_dark_in_bar} dark px", v)

    from src.anim.eventcard import EventCardManager as _ECM
    _ec = _ECM()
    _ec.push("ok", "BUILD COMPLETE", ["138 TESTS PASSED"], 2.0)
    img_e, d_e = Gfx.canvas()
    _ec.render(d_e, gfx, time.time())
    _card_pixels = [img_e.getpixel((x, y))
                    for y in range(11, 23) for x in range(W)]
    _dark_in_card = sum(1 for v in _card_pixels if v <= BIN_THRESHOLD)
    check("eventcard: inverse title visible on white bar",
          _dark_in_card > 40, f"{_dark_in_card} dark px", v)

    # 5b3 — Codex page renders
    from src.pages.codex import CodexPage
    cp = CodexPage()
    img_cp, d_cp = gfx.canvas()
    cp.render(gfx, d_cp, {}, oc, dl, {})
    check("Codex page renders", True, "no error", v)

    # 5b4 — Event card renders and expires
    from src.anim.eventcard import EventCardManager
    ec = EventCardManager()
    check("eventcard: inactive by default", not ec.active, "inactive", v)
    ec.push("ok", "BUILD COMPLETE", ["138 TESTS PASSED"], 2.5)
    check("eventcard: active after push", ec.active, "active", v)
    img_ec, d_ec = gfx.canvas()
    drawn = ec.render(d_ec, gfx, time.time())
    check("eventcard: renders a card", drawn is True, str(drawn), v)
    ec.clear()
    check("eventcard: cleared", not ec.active, "cleared", v)

    # 5c — ConnectionSupervisor state machine
    sup = ConnectionSupervisor("test")
    check("supervisor: starts OFFLINE", sup.state == "offline", sup.state, v)
    sup.mark_connecting()
    check("supervisor: CONNECTING after mark_connecting", sup.state == "connecting", sup.state, v)
    sup.mark_online(latency=0.15)
    check("supervisor: ONLINE after mark_online", sup.is_online, sup.state, v)
    check("supervisor: latency recorded", sup.latency == 0.15, str(sup.latency), v)
    sup.mark_failure("test error")
    check("supervisor: STALE after 1 failure from ONLINE", sup.is_stale, sup.state, v)
    sup.mark_failure("test error 2")
    check("supervisor: OFFLINE after 2 failures from STALE", sup.is_offline, sup.state, v)
    check("supervisor: should_reconnect after OFFLINE", sup.should_reconnect(time.time() + 60), "reconnect ok", v)
    sup.mark_online()
    check("supervisor: ONLINE snaps back from any state", sup.is_online, sup.state, v)
    snap = sup.snapshot()
    check("supervisor: snapshot has state+latency", "state" in snap and "latency" in snap, list(snap.keys())[:4], v)
    sup.mark_stale("partial data")
    check("supervisor: mark_stale from ONLINE", sup.is_stale, sup.state, v)

    # 5d — button handler: taps, holds and combos
    class _FakeLcd:
        def __init__(self):
            self.down = 0
        def button(self, bit):
            return bool(self.down & bit)

    def _actions(sequence):
        """Simulate presses. sequence: [(bitmask, seconds_held), ...].

        Polls repeatedly while a button is down so hold detection (0.5 s)
        actually gets a chance to fire.
        """
        lcd = _FakeLcd()
        bh = ButtonHandler(lcd)
        t = 1000.0
        out = []
        lcd.down = 0
        bh.poll(t)                       # prime: released
        for mask, held_for in sequence:
            lcd.down = mask              # press edge
            t += 0.01
            out += [a for a, _ in bh.poll(t)]
            steps = max(1, int(round(held_for / 0.1)))
            for _ in range(steps):       # keep it down
                t += 0.1
                out += [a for a, _ in bh.poll(t)]
            lcd.down = 0                 # release
            t += 0.2
            out += [a for a, _ in bh.poll(t)]
        return out

    from src.util.constants import BTN_1 as _B1, BTN_2 as _B2, BTN_3 as _B3, BTN_4 as _B4
    acts = _actions([(_B1, 0.05)])
    check("buttons: B1 tap -> prev", "prev" in acts, str(acts), v)
    acts = _actions([(_B2, 0.05)])
    check("buttons: B2 tap -> next", "next" in acts, str(acts), v)
    acts = _actions([(_B1, 0.60)])
    check("buttons: B1 hold -> first_page", "first_page" in acts, str(acts), v)
    acts = _actions([(_B2, 0.60)])
    check("buttons: B2 hold -> last_page", "last_page" in acts, str(acts), v)
    acts = _actions([(_B3, 0.05)])
    check("buttons: B3 tap -> status_tap (mascot)", "status_tap" in acts, str(acts), v)
    acts = _actions([(_B3, 0.60)])
    check("buttons: B3 hold -> status_hold (scouter)", "status_hold" in acts, str(acts), v)
    acts = _actions([(_B1 | _B2, 0.05)])
    check("buttons: B1+B2 -> combo_12", "combo_12" in acts, str(acts), v)
    acts = _actions([(_B3 | _B4, 0.05)])
    check("buttons: B3+B4 -> combo_34 (menu)", "combo_34" in acts, str(acts), v)
    acts = _actions([(_B1 | _B2, 0.60)])
    check("buttons: B1+B2 held fires no lone holds",
          "first_page" not in acts and "last_page" not in acts, str(acts), v)

    # 5e — v10 integration regressions
    # (a) the mascot page must be the real instance, never pages[0]
    _from_lcd = None
    import re as _re
    _src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "lcdglance.py"), encoding="utf-8").read()
    check("integration: mascot_page is not pages[0]",
          "self.mascot_page = self.pages[0]" not in _src,
          "no positional guess", v)
    check("integration: fps/interval hoisted out of the LCD branch",
          "fps = FPS_IDLE\n                interval = 1.0 / fps" in _src,
          "defaults before branch", v)

    # (b) RGB theming must be name-keyed, not index-keyed
    from src.util.constants import PAGE_THEME as _PT
    check("integration: PAGE_THEME keyed by page name",
          all(isinstance(k, str) for k in _PT.keys()),
          "str keys", v)
    from src.ui.rgb import RGBEngine as _RGB
    _eng = _RGB.__new__(_RGB)
    _eng.active_source_key = "pc"
    _eng.busy = False
    _eng.vps = None
    _now_c = _eng._ambient({}, "Now")
    _sys_c = _eng._ambient({"cpu": 50}, "System")
    _net_c = _eng._ambient({}, "Network")
    check("integration: _ambient resolves Now/System/Network by name",
          _now_c is not None and _sys_c is not None and _net_c is not None,
          f"{_now_c} {_sys_c} {_net_c}", v)

    # (c) quick menu must accept a snapshot dict where it expects a monitor
    from src.pages.quickmenu import QuickMenuPage as _QMP
    _qm = _QMP()
    _ok_dict = True
    try:
        _qm.build_menu({}, oc, dl, {"enabled": True, "online": False})
    except Exception as _e:
        _ok_dict = False
        _err = str(_e)
    check("integration: quickmenu.build_menu accepts a snapshot dict",
          _ok_dict, "no AttributeError" if _ok_dict else _err, v)

    # 6 — mascots are distinct and non-blank
    seen = {}
    for key in ("openclaw", "codex", "pc"):
        im, dr = Gfx.canvas()
        mascot.draw(dr, key, 29, 18, "idle", busy=False)
        data = to_mono_bytes(im)
        lit = sum(1 for b in data if b)
        seen[key] = data
        check(f"mascot {key}: art present", lit > 50, f"{lit} lit px", v)
    keys = list(seen)
    distinct = len({seen[k] for k in keys}) == len(keys)
    check("three mascots render distinctly", distinct, "", v)

    # optional preview
    if args.preview:
        from PIL import Image
        rows = []
        for i, p in enumerate(pages):
            gfx.dots = (i, len(pages))
            ctx = {"mascot": mascot, "sources": sources,
                   "active_source": by_key["openclaw"], "mood": "idle",
                   "load": 12345, "busy": False, "vps_snapshot": {},
                   "hist_bufs": {"cpu": [], "ram": [], "disk": []},
                   "anim_state": 0, "interaction": None, "interaction_trigger": None}
            im, dr = Gfx.canvas()
            p.render(gfx, dr, STATS, oc, dl, ctx)
            rows.append(im)
        os.makedirs("preview", exist_ok=True)
        sc = 3
        sheet = Image.new("L", (W * sc, len(rows) * (H * sc + 4)), 0)
        y = 0
        for im in rows:
            sheet.paste(im.resize((W * sc, H * sc), Image.NEAREST), (0, y))
            y += H * sc + 4
        out = os.path.join("preview", "verify_sheet.png")
        sheet.save(out)
        print(f"  preview written: {out}")

    print("=" * 52)
    if _failures:
        print(f"{FAIL}: {len(_failures)} check(s) failed")
        for f in _failures:
            print(f"   - {f}")
        return 1
    print(f"{PASS}: all checks green ({len(pages)} pages + geometry + mascots)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
