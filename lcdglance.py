#!/usr/bin/env python3
"""
LCDGlance v9.1 — Logitech G510 (160×43 mono LCD), modular edition.

Architecture:
  src/          Package with all subsystems
    hardware/   LCD and LED DLL controllers
    sources/    System stats, OpenClaw, download, VPS monitors
    render/     Gfx toolkit, bitmap conversion, native bitmap fonts
    anim/       AnimationController, SceneDirector, transitions, toasts
    mascots/    MascotRenderer, SpriteSet, interactions, source logic
    pages/      All page renderers (including screensaver & quick menu)
    ui/         ButtonHandler, RGBEngine, applet killer
    util/       Constants, text helpers, RingBuffer

New in v9:
  - Modular package structure (was a single 2062-line file)
  - AnimationController: state machine for mascot expressions + dynamic FPS
  - SceneDirector: page selection, auto-focus, overrides, transitions
  - TransitionEngine: slide/wipe/dissolve between pages
  - ToastManager: notification overlays without page switches
  - ButtonHandler: tap, hold (0.5s), and combo detection (B1+B2, B3+B4)
  - RingBuffer: thread-safe history for CPU/RAM/disk/net sparklines
  - Dynamic FPS: 4 idle, 8 animated, 12 busy, 24 transitions
  - Live HH:MM clock in the header of every page (never overlaps content)
  - B3 cycles the featured mascot (AUTO -> PC -> CLAW -> CODEX)
  - Screensaver page (clock + sleeping mascot after 90s idle)
  - Quick menu page (B3+B4 hold combo for context actions)
  - All v7.1 functionality preserved with zero regression

Mascot rendering is PROCEDURAL (hand-drawn with Pillow primitives). An
optional sprite renderer exists behind constants.USE_SPRITES; it is off
because pixel-art aliases badly on the real 1-bit panel.
"""

import threading
import time
import traceback

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from PIL import Image, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from src.util.constants import (
    W, H, BITMAP_SIZE, LOOP_INTERVAL, RENDER_MIN_GAP,
    RESUBMIT_AFTER, LCD_RECONNECT, OC_POLL_INTERVAL, DL_POLL_INTERVAL,
    APP_KILL_INTERVAL, FPS_IDLE, FPS_ANIMATED, FPS_BUSY, FPS_TRANSITION,
    BTN_1, BTN_2, BTN_3, BTN_4, USE_SPRITES,
)
from src.util.text import ascii_text, clip, fmt_speed, fmt_bytes, fmt_uptime, age_str
from src.util.ringbuf import RingBuffer
from src.render.bitmap import to_mono_bytes, mono_to_image
from src.render.gfx import Gfx
from src.hardware.lcd import LCDController
from src.hardware.led import LEDController
from src.sources.system import (
    get_system_stats, NET_HIST, NET_HIST_BUF,
    CPU_HIST_BUF, RAM_HIST_BUF, DISK_HIST_BUF,
)
from src.sources.openclaw import OpenClawMonitor
from src.sources.download import DownloadDetector
from src.sources.vps import VPSMonitor
from src.mascots.mascot import MascotRenderer
from src.mascots.sprites import create_default_sprites
from src.mascots.sources import build_sources, pick_active, mood_for, load_index, is_busy
from src.mascots.interactions import find_interaction
from src.pages.mascot import MascotPage
from src.pages.sources import SourcesPage
from src.pages.system import SystemPage
from src.pages.network import NetworkPage
from src.pages.procs import ProcsPage
from src.pages.openclaw_page import OpenClawPage
from src.pages.alerts import AlertsPage
from src.pages.status import StatusPage
from src.pages.download import DownloadPage
from src.pages.vps_page import VPSPage
from src.pages.screensaver import ScreensaverPage
from src.pages.quickmenu import QuickMenuPage
from src.anim.controller import AnimationController, AnimState
from src.anim.scene import SceneDirector
from src.anim.transition import TransitionEngine
from src.anim.toast import ToastManager
from src.ui.buttons import ButtonHandler
from src.ui.rgb import RGBEngine
from src.ui.applets import kill_lcd_applets

try:
    from PIL import ImageOps as _ImageOps
except ImportError:
    _ImageOps = None


class LCDGlance:
    """Main application: owns hardware, monitors, pages, and the render loop."""

    def __init__(self):
        # Hardware
        self.lcd = LCDController()
        self.led = LEDController()

        # Data sources
        self.oc = OpenClawMonitor()
        self.dl = DownloadDetector()
        self.vps = VPSMonitor()

        # Rendering
        self.gfx = Gfx()
        # Sprites are opt-in (constants.USE_SPRITES); procedural reads better.
        self.sprites = create_default_sprites() if USE_SPRITES else None
        self.mascot = MascotRenderer(self.gfx, sprites=self.sprites)

        # Animation engine
        self.anim = AnimationController()
        self.scene = None  # initialised after pages
        self.transition = TransitionEngine()
        self.toast = ToastManager()
        self.buttons = None  # initialised after LCD connect
        self.screensaver = ScreensaverPage()
        self.quickmenu = QuickMenuPage()

        # RGB
        self.rgb = None

        # Pages
        self.pages = [MascotPage(), SourcesPage(), SystemPage(), NetworkPage(),
                      ProcsPage(), OpenClawPage(), AlertsPage()]
        if self.vps.enabled:
            self.pages.append(VPSPage())
        self.mascot_page = self.pages[0]
        self.status_page = StatusPage()
        self.dl_page = DownloadPage()

        # Scene director
        self.scene = SceneDirector(self.pages, self.mascot_page, self.dl_page, self.status_page)

        # State
        self.running = False
        self._last_bitmap = None
        self._last_submit = 0.0
        self._last_render = 0.0
        self._in_screensaver = False
        self._in_quickmenu = False
        self._last_input = time.time()
        # Mascot cycling (B3): None=auto, else forced source key
        self._MASCOT_CYCLE = [None, "pc", "openclaw", "codex"]
        self._mascot_cycle_idx = 0
        self._mascot_override = None

    # ---- lifecycle
    def start(self):
        print("LCDGlance v9.1 — G510 mascots + RGB + animations + clock", flush=True)
        print("=" * 60, flush=True)

        if not HAS_PIL:
            print("[!] Pillow missing — graphics unavailable", flush=True)
            return
        if not HAS_PSUTIL:
            print("[!] psutil missing — stats unavailable", flush=True)

        kill_lcd_applets()
        self.lcd.connect()
        self.led.connect()
        self.rgb = RGBEngine(self.led, self.oc, self.dl, self.vps)
        self.buttons = ButtonHandler(self.lcd)

        if not self.lcd.connected and not self.led.connected:
            print("[!] No Logitech devices. Is LGS running?", flush=True)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return

        self.running = True
        print(f"Pages: {[p.name for p in self.pages]}", flush=True)
        print("B1/B2 pages  B3 mascot  B3-hold scouter  B4 flash  B3+B4 menu  B1+B2 cycle", flush=True)
        print("Animations: controller + scene director + transitions + toasts", flush=True)
        if self.vps.enabled:
            print(f"VPS: {self.vps.user}@{self.vps.host} (poll {self.vps.poll_interval}s)", flush=True)
        else:
            print("VPS: disabled (no host in vps_config.json)", flush=True)

        self._splash()
        self.rgb.sweep()

        threading.Thread(target=self._oc_loop, daemon=True).start()
        threading.Thread(target=self._dl_loop, daemon=True).start()
        if self.vps.enabled:
            threading.Thread(target=self._vps_loop, daemon=True).start()

        try:
            self._loop()
        except KeyboardInterrupt:
            print("\nStopping...", flush=True)
        finally:
            self.stop()

    def _splash(self):
        """Show a startup splash screen for 2 seconds."""
        img, d = self.gfx.canvas()
        self.mascot.draw(d, "openclaw", 28, 21, "happy")
        self.gfx.text(d, (56, 6), "LCDGlance v9.1")
        self.gfx.text(d, (56, 20), "PC / CLAW / CODEX", small=True)
        self.gfx.text(d, (56, 31), "mascots + clock", small=True)
        if self.lcd.connected:
            self.lcd.submit(to_mono_bytes(img))
            self.lcd.update()
            time.sleep(2.0)

    def _oc_loop(self):
        try:
            self.oc.poll()
        except Exception:
            pass
        while self.running:
            try:
                time.sleep(OC_POLL_INTERVAL)
                if not self.running:
                    break
                try:
                    self.oc.poll()
                except Exception:
                    pass
            except Exception:
                traceback.print_exc()
                time.sleep(1.0)

    def _dl_loop(self):
        while self.running:
            try:
                self.dl.poll(get_system_stats())
            except Exception:
                pass
            time.sleep(DL_POLL_INTERVAL)

    def _vps_loop(self):
        try:
            self.vps.poll()
        except Exception:
            pass
        while self.running:
            try:
                time.sleep(self.vps.poll_interval)
                if not self.running:
                    break
                try:
                    self.vps.poll()
                except Exception:
                    pass
            except Exception:
                traceback.print_exc()
                time.sleep(1.0)

    def _safe_poll(self):
        try:
            self.oc.poll()
        except Exception:
            pass

    # ---- main loop
    def _loop(self):
        reconnect_at = kill_at = 0.0

        while self.running:
            try:
                now = time.time()

                # Periodic LCD reconnection check
                if now - reconnect_at > LCD_RECONNECT:
                    self.lcd.ensure_connected()
                    reconnect_at = now

                # Periodic LGS applet sweep
                if now - kill_at > APP_KILL_INTERVAL:
                    kill_lcd_applets()
                    kill_at = now

                # Collect system stats
                st = get_system_stats()

                # Process buttons
                if self.buttons:
                    actions = self.buttons.poll(now)
                    for action, param in actions:
                        self._last_input = now
                        self.screensaver.feed_input(now)

                        if self._in_quickmenu:
                            if action == "prev":
                                self.quickmenu.prev_item()
                            elif action == "next":
                                self.quickmenu.next_item()
                            elif action == "status_tap":
                                # Select current menu item
                                act = self.quickmenu.select()
                                self._in_quickmenu = False
                                self._execute_menu_action(act, st)
                            elif action == "flash_tap":
                                self._in_quickmenu = False
                            continue

                        # Normal button handling
                        if action == "prev":
                            old_page = self.scene.page_index
                            self.scene.prev_page()
                            self._start_transition_if_page_changed(old_page)
                        elif action == "next":
                            old_page = self.scene.page_index
                            self.scene.next_page()
                            self._start_transition_if_page_changed(old_page)
                        elif action == "status_tap":
                            # B3 tap: jump to the Mascot page and cycle the
                            # featured mascot (AUTO -> PC -> CLAW -> CODEX).
                            self._cycle_mascot()
                        elif action == "status_hold":
                            # B3 hold: Scouter readout (power level + temps).
                            threading.Thread(target=self._safe_poll, daemon=True).start()
                            self.scene.show_status(8.0)
                            self.anim.push(AnimState.ALERT, 8.0)
                        elif action == "flash_tap":
                            self.scene.flash(0.7)
                            if self.rgb:
                                self.rgb.manual_alert = not self.rgb.manual_alert
                                if not self.rgb.manual_alert:
                                    self.led.stop_effects()
                        elif action == "flash_hold":
                            self.scene.flash(1.5)
                            self.anim.push(AnimState.ALERT, 1.5)
                        elif action == "combo_12":
                            # Quick cycle through pages
                            for _ in range(3):
                                self.scene.next_page()
                        elif action == "combo_34":
                            # Open quick menu
                            self._in_quickmenu = True
                            self.quickmenu.build_menu(st, self.oc, self.dl, self.vps)

                # Update scene (auto-focus for downloads, agent events)
                self.scene.update(now, self.oc, self.dl)

                # Build context
                sources = build_sources(st, self.oc, self.dl)
                active = pick_active(sources)
                active = self._apply_mascot_override(sources, active)
                load = load_index(st, self.oc, self.dl)
                busy = is_busy(st, self.oc, self.dl, active)

                # Check for mascot interaction (two sources active)
                interaction = find_interaction(sources)
                oc_snap = self.oc.snapshot()
                ev = oc_snap.get("last_event")
                interaction_trigger = None
                if ev and (now - ev["ts"]) < 3.0:
                    interaction_trigger = "success" if ev["kind"] == "ok" else "failure"

                # Screensaver: only while genuinely idle. It is a rest screen,
                # so any real work (agents running, a download, heavy CPU, a
                # fresh event) must wake it and keep it on the working view.
                working = bool(
                    busy
                    or interaction_trigger
                    or self.dl.active
                    or (ev and (now - ev["ts"]) < 8.0)
                )
                if working:
                    self.screensaver.feed_activity(now)
                if not self._in_quickmenu:
                    if self._in_screensaver:
                        if working or (now - self.screensaver.last_input) < 2.0:
                            self._in_screensaver = False
                            if busy or self.dl.active:
                                # Surface the reacting mascot, not the old page
                                self.scene.focus(self.scene.mascot_page, 6.0, "wake")
                    elif self.screensaver.should_show(now, busy=working):
                        self._in_screensaver = True

                # Advance animation controller
                anim_state = self.anim.tick(now)

                # Update RGB
                if self.rgb:
                    self.rgb.active_source_key = active["key"]
                    self.rgb.busy = busy
                    self.rgb.update(st, self.scene.page_index)

                # Push toasts for notable events
                if ev and (now - ev["ts"]) < 2.0:
                    if ev["kind"] == "ok":
                        self.toast.push(f"OK: {clip(ev.get('label', ''), 20)}", "ok", 2.5)
                    else:
                        self.toast.push(f"FAIL: {clip(ev.get('label', ''), 20)}", "error", 3.0)

                # Render LCD frame
                if self.lcd.connected:
                    # Determine which page to render
                    if self._in_quickmenu:
                        page = self.quickmenu
                    elif self._in_screensaver:
                        page = self.screensaver
                    else:
                        page = self.scene.current_page

                    # Determine animation rate
                    if self._in_screensaver:
                        fps = 2  # screensaver: very slow
                    elif self._in_quickmenu:
                        fps = 4  # menu: static
                    elif self.scene.is_animated or busy:
                        fps = FPS_BUSY if anim_state >= AnimState.ALERT else FPS_ANIMATED
                    else:
                        fps = FPS_IDLE
                    interval = 1.0 / fps

                    if now - self._last_render >= interval:
                        self._last_render = now
                        self.gfx.dots = (self.scene.page_index, len(self.pages))

                        # Build history buffers context
                        hist_bufs = {
                            "cpu": CPU_HIST_BUF.values,
                            "ram": RAM_HIST_BUF.values,
                            "disk": DISK_HIST_BUF.values,
                        }

                        ctx = {
                            "mascot": self.mascot, "sources": sources,
                            "active_source": active,
                            "mood": mood_for(st, self.oc, self.dl, active),
                            "load": load, "busy": busy,
                            "vps_snapshot": self.vps.snapshot(),
                            "hist_bufs": hist_bufs,
                            "anim_state": anim_state,
                            "interaction": interaction,
                            "interaction_trigger": interaction_trigger,
                        }

                        img, d = self.gfx.canvas()
                        page.render(self.gfx, d, st, self.oc, self.dl, ctx)

                        # Toast overlay (not in screensaver/quickmenu)
                        if not self._in_screensaver and not self._in_quickmenu:
                            self.toast.render(d, self.gfx, now)

                        # Flash overlay (B4)
                        if now < self.scene.flash_until:
                            if _ImageOps:
                                img = _ImageOps.invert(img)

                        data = to_mono_bytes(img)

                        # Transition blending
                        trans_data = self.transition.render(now)
                        if trans_data:
                            data = trans_data

                        # Skip identical frames (biggest optimisation)
                        if data != self._last_bitmap or now - self._last_submit > RESUBMIT_AFTER:
                            self.lcd.submit(data)
                            self._last_bitmap = data
                            self._last_submit = now

                time.sleep(LOOP_INTERVAL)
            except Exception:
                traceback.print_exc()
                time.sleep(1.0)

    def _apply_mascot_override(self, sources, active):
        """If the user forced a mascot with B3, return that source instead."""
        key = self._mascot_override
        if key is None:
            return active
        for s in sources:
            if s["key"] == key:
                return s
        return active

    def _cycle_mascot(self):
        """B3: step to the next mascot and jump to the Mascot page."""
        self._mascot_cycle_idx = (self._mascot_cycle_idx + 1) % len(self._MASCOT_CYCLE)
        self._mascot_override = self._MASCOT_CYCLE[self._mascot_cycle_idx]
        label = "AUTO" if self._mascot_override is None else self._mascot_override.upper()
        # Jump to the Mascot page so the change is immediately visible
        try:
            self.scene.page_index = self.pages.index(self.mascot_page)
        except (ValueError, AttributeError):
            self.scene.page_index = 0
        self.toast.push(f"MASCOT {label}", "info", 1.6)

    def _start_transition_if_page_changed(self, old_index):
        """If the page changed, start a transition animation."""
        new_index = self.scene.page_index
        if new_index != old_index and self.lcd.connected and self._last_bitmap:
            st = get_system_stats()
            sources = build_sources(st, self.oc, self.dl)
            active = pick_active(sources)
            active = self._apply_mascot_override(sources, active)
            load = load_index(st, self.oc, self.dl)
            busy_flag = is_busy(st, self.oc, self.dl, active)
            self.gfx.dots = (new_index, len(self.pages))
            hist_bufs = {
                "cpu": CPU_HIST_BUF.values,
                "ram": RAM_HIST_BUF.values,
                "disk": DISK_HIST_BUF.values,
            }
            ctx = {
                "mascot": self.mascot, "sources": sources,
                "active_source": active,
                "mood": mood_for(st, self.oc, self.dl, active),
                "load": load, "busy": busy_flag,
                "vps_snapshot": self.vps.snapshot(),
                "hist_bufs": hist_bufs,
                "anim_state": AnimState.TRANSITION,
                "interaction": None, "interaction_trigger": None,
            }
            img_new, d_new = self.gfx.canvas()
            self.scene.current_page.render(self.gfx, d_new, st, self.oc, self.dl, ctx)
            new_data = to_mono_bytes(img_new)
            self.transition.start(self._last_bitmap, new_data)

    def _execute_menu_action(self, action, st):
        """Execute a quick menu action."""
        if action == "poll":
            threading.Thread(target=self._safe_poll, daemon=True).start()
            self.toast.push("Polling OpenClaw...", "info", 2.0)
        elif action == "restart_gw":
            # Would need subprocess to restart OpenClaw
            self.toast.push("Restart not yet wired", "warn", 2.0)
        elif action == "taskmgr":
            import subprocess
            subprocess.Popen(["taskmgr.exe"], creationflags=0x08000000)
            self.toast.push("Task Manager opened", "ok", 1.5)
        elif action == "vps_reconnect" or action == "vps_retry":
            threading.Thread(target=self.vps.poll, daemon=True).start()
            self.toast.push("VPS reconnecting...", "info", 2.0)
        elif action == "dns_flush":
            import subprocess
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, creationflags=0x08000000)
            self.toast.push("DNS flushed", "ok", 1.5)
        elif action == "net_reset":
            self.toast.push("Net reset not yet wired", "warn", 2.0)
        elif action == "screensaver":
            self._in_screensaver = True
            # Push both timers far in the past so it stays on until real
            # input or activity wakes it.
            self.screensaver.feed_input(time.time() - 400)
            self.screensaver.last_activity = 0.0

    def stop(self):
        self.running = False
        self.lcd.shutdown()
        self.led.shutdown()
        print("LCDGlance stopped.", flush=True)


if __name__ == "__main__":
    LCDGlance().start()
